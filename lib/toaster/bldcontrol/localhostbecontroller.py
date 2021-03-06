#
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# BitBake Toaster Implementation
#
# Copyright (C) 2014        Intel Corporation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


import os
import sys
import re
import shutil
from django.db import transaction
from django.db.models import Q
from bldcontrol.models import BuildEnvironment, BRLayer, BRVariable, BRTarget, BRBitbake
from orm.models import CustomImageRecipe, Layer, Layer_Version, ProjectLayer
from orm.models import ToasterSetting
import subprocess

from toastermain import settings

from bldcontrol.bbcontroller import BuildEnvironmentController, ShellCmdException, BuildSetupException, BitbakeController

import logging
logger = logging.getLogger("toaster")

from pprint import pprint, pformat

class LocalhostBEController(BuildEnvironmentController):
    """ Implementation of the BuildEnvironmentController for the localhost;
        this controller manages the default build directory,
        the server setup and system start and stop for the localhost-type build environment

    """

    def __init__(self, be):
        super(LocalhostBEController, self).__init__(be)
        self.pokydirname = None
        self.islayerset = False

    def _shellcmd(self, command, cwd=None, nowait=False,env=None):
        if cwd is None:
            cwd = self.be.sourcedir
        if env is None:
            env=os.environ.copy()

        logger.debug("lbc_shellcmd: (%s) %s" % (cwd, command))
        p = subprocess.Popen(command, cwd = cwd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        if nowait:
            return
        (out,err) = p.communicate()
        p.wait()
        if p.returncode:
            if len(err) == 0:
                err = "command: %s \n%s" % (command, out)
            else:
                err = "command: %s \n%s" % (command, err)
            logger.warning("localhostbecontroller: shellcmd error %s" % err)
            raise ShellCmdException(err)
        else:
            logger.debug("localhostbecontroller: shellcmd success")
            return out.decode('utf-8')

    def getGitCloneDirectory(self, url, branch):
        """Construct unique clone directory name out of url and branch."""
        if branch != "HEAD":
            return "_toaster_clones/_%s_%s" % (re.sub('[:/@+%]', '_', url), branch)

        # word of attention; this is a localhost-specific issue; only on the localhost we expect to have "HEAD" releases
        # which _ALWAYS_ means the current poky checkout
        from os.path import dirname as DN
        local_checkout_path = DN(DN(DN(DN(DN(os.path.abspath(__file__))))))
        #logger.debug("localhostbecontroller: using HEAD checkout in %s" % local_checkout_path)
        return local_checkout_path

    ### WIND_RIVER_EXTENSION_BEGIN ###
    def proccessSetupLayerXml(self, name, dirpath, giturl, commit, localdirname,git_env):
        repo_xml=os.path.join(ToasterSetting.objects.get(name = 'SETUP_XMLDIR').value,name+'.xml')
        logger.debug("proccessSetupLayerXml: looking for setup xml %s" % repo_xml)
        xml_remotes={}
        xml_remotes['base']=ToasterSetting.objects.get(name = 'SETUP_GITURL').value
        if ToasterSetting.objects.filter(name='SETUP_PATH_FILTER').count() == 1:
            xml_path_filter=ToasterSetting.objects.get(name = 'SETUP_PATH_FILTER').value
        else:
            xml_path_filter=''

        if os.path.exists(repo_xml):
            logger.debug("proccessSetupLayerXml: processing setup xml %s" % repo_xml)
            import xml.etree.ElementTree
            with open(repo_xml,"r") as logfile:
                for line in logfile:
                    if 0 == len(line.strip()):
                        continue
                    e = xml.etree.ElementTree.XML(line)
                    xml_name=e.get('name')
                    xml_remote=os.path.join(xml_remotes[e.get('remote')],xml_name)
                    xml_path=e.get('path')
                    if xml_path_filter:
                        # substitution on xml path: 's|<regex>|xyz|'
                        if xml_path_filter.startswith('s'):
                            filter_params=xml_path_filter.split(xml_path_filter[1])
                            xml_path=re.sub(filter_params[1],filter_params[2], xml_path)
                            if xml_path.startswith('/'):
                                xml_path=xml_path[1:]
                    xml_path=os.path.join(localdirname,xml_path)
                    xml_bare=e.get('bare')
                    # clone and insert the sub-layer repo
                    if not os.path.exists(xml_path):
                        if "True" == xml_bare:
                            self._shellcmd('git clone --bare "%s" "%s"' % (xml_remote, xml_path),env=git_env)
                        else:
                            self._shellcmd('git clone "%s" "%s"' % (xml_remote, xml_path),env=git_env)
                            ref = commit if re.match('^[a-fA-F0-9]+$', commit) else 'origin/%s' % commit
                            try:
                                self._shellcmd('git fetch --all && git reset --hard "%s"' % ref, xml_path,env=git_env)
                            except:
                                logger.debug("localhostbecontroller: XML Warning commit %s not present in repo '%s'" % (commit, name))
    ### WIND_RIVER_EXTENSION_END ###

    def setCloneStatus(self,bitbake,status,total,current):
        bitbake.req.build.repos_cloned=current
        bitbake.req.build.repos_to_clone=total
        bitbake.req.build.save()

    def setLayers(self, bitbake, layers, targets):
        """ a word of attention: by convention, the first layer for any build will be poky! """

        assert self.be.sourcedir is not None

        layerlist = []
        nongitlayerlist = []

        # append anspass environment if present
        git_env = os.environ.copy()
        toaster_anspass_data=os.path.join(self.be.sourcedir,'.toaster_anspass')
        if os.path.exists(toaster_anspass_data):
            with open(toaster_anspass_data,"r") as anspassfile:
                for line in anspassfile:
                    name,value = line.strip().split('=')
                    git_env[name]=value

        # set layers in the layersource

        # 1. get a list of repos with branches, and map dirpaths for each layer
        gitrepos = {}

        # if we're using a remotely fetched version of bitbake add its git
        # details to the list of repos to clone
        if bitbake.giturl and bitbake.commit:
            gitrepos[(bitbake.giturl, bitbake.commit)] = []
            gitrepos[(bitbake.giturl, bitbake.commit)].append(
                ("bitbake", bitbake.dirpath))

        for layer in layers:
            # We don't need to git clone the layer for the CustomImageRecipe
            # as it's generated by us layer on if needed
            if CustomImageRecipe.LAYER_NAME in layer.name:
                continue

            # If we have local layers then we don't need clone them
            # For local layers giturl will be empty
            if not layer.giturl:
                nongitlayerlist.append(layer.layer_version.layer.local_source_dir)
                continue

            if not (layer.giturl, layer.commit) in gitrepos:
                gitrepos[(layer.giturl, layer.commit)] = []
            gitrepos[(layer.giturl, layer.commit)].append( (layer.name, layer.dirpath) )


        logger.debug("localhostbecontroller, our git repos are %s" % pformat(gitrepos))


        # 2. Note for future use if the current source directory is a
        # checked-out git repos that could match a layer's vcs_url and therefore
        # be used to speed up cloning (rather than fetching it again).

        cached_layers = {}

        try:
            for remotes in self._shellcmd("git remote -v", self.be.sourcedir).split("\n"):
                try:
                    remote = remotes.split("\t")[1].split(" ")[0]
                    if remote not in cached_layers:
                        cached_layers[remote] = self.be.sourcedir
                except IndexError:
                    pass
        except ShellCmdException:
            # ignore any errors in collecting git remotes this is an optional
            # step
            pass

        logger.info("Using pre-checked out source for layer %s", cached_layers)

        # 3. checkout the repositories
        clone_count=0
        clone_total=len(gitrepos.keys())
        self.setCloneStatus(bitbake,'Started',clone_total,clone_count)
        for giturl, commit in gitrepos.keys():
            self.setCloneStatus(bitbake,'progress',clone_total,clone_count)
            clone_count += 1

            localdirname = os.path.join(self.be.sourcedir, self.getGitCloneDirectory(giturl, commit))
            logger.debug("localhostbecontroller: giturl %s:%s checking out in current directory %s" % (giturl, commit, localdirname))

            # see if our directory is a git repository
            if os.path.exists(localdirname):
                try:
                    localremotes = self._shellcmd("git remote -v",
                                                  localdirname)
                    if not giturl in localremotes and commit != 'HEAD':
                        raise BuildSetupException("Existing git repository at %s, but with different remotes ('%s', expected '%s'). Toaster will not continue out of fear of damaging something." % (localdirname, ", ".join(localremotes.split("\n")), giturl))
                except ShellCmdException:
                    # our localdirname might not be a git repository
                    #- that's fine
                    pass
            else:
                if giturl in cached_layers:
                    logger.debug("localhostbecontroller git-copying %s to %s" % (cached_layers[giturl], localdirname))
                    self._shellcmd("git clone \"%s\" \"%s\"" % (cached_layers[giturl], localdirname),env=git_env)
                    self._shellcmd("git remote remove origin", localdirname,env=git_env)
                    self._shellcmd("git remote add origin \"%s\"" % giturl, localdirname,env=git_env)
                else:
                    logger.debug("localhostbecontroller: cloning %s in %s" % (giturl, localdirname))
                    self._shellcmd('git clone "%s" "%s"' % (giturl, localdirname),env=git_env)

            # branch magic name "HEAD" will inhibit checkout
            if commit != "HEAD":
                logger.debug("localhostbecontroller: checking out commit %s to %s " % (commit, localdirname))
                ref = commit if re.match('^[a-fA-F0-9]+$', commit) else 'origin/%s' % commit
                self._shellcmd('git fetch --all && git reset --hard "%s"' % ref, localdirname,env=git_env)

            # take the localdirname as poky dir if we can find the oe-init-build-env
            if self.pokydirname is None and os.path.exists(os.path.join(localdirname, "oe-init-build-env")):
                logger.debug("localhostbecontroller: selected poky dir name %s" % localdirname)
                self.pokydirname = localdirname

                # make sure we have a working bitbake
                if not os.path.exists(os.path.join(self.pokydirname, 'bitbake')):
                    logger.debug("localhostbecontrollerFOO3: checking bitbake into the poky dirname %s " % self.pokydirname)
                    self._shellcmd("git clone -b \"%s\" \"%s\" \"%s\" " % (bitbake.commit, bitbake.giturl, os.path.join(self.pokydirname, 'bitbake')),env=git_env)

            # verify our repositories
            for name, dirpath in gitrepos[(giturl, commit)]:
                localdirpath = os.path.join(localdirname, dirpath)
                logger.debug("localhostbecontroller: localdirpath expected '%s'" % localdirpath)
                if not os.path.exists(localdirpath):
                    raise BuildSetupException("Cannot find layer git path '%s' in checked out repository '%s:%s'. Aborting." % (localdirpath, giturl, commit))

                if name != "bitbake":
                    layerlist.append(localdirpath.rstrip("/"))

            ### WIND_RIVER_EXTENSION_BEGIN ###
            # process XML layer extensions
            for name, dirpath in gitrepos[(giturl, commit)]:
                self.proccessSetupLayerXml(name, dirpath, giturl, commit, localdirname, git_env)
            ### WIND_RIVER_EXTENSION_END ###

        self.setCloneStatus(bitbake,'complete',clone_total,clone_count)
        logger.debug("localhostbecontroller: current layer list %s " % pformat(layerlist))

        # 5. create custom layer and add custom recipes to it
        layerpath = os.path.join(self.be.builddir,
                                 CustomImageRecipe.LAYER_NAME)
        for target in targets:
            try:
                customrecipe = CustomImageRecipe.objects.get(name=target.target,
                                                             project=bitbake.req.project)
            except CustomImageRecipe.DoesNotExist:
                continue # not a custom recipe, skip

            # create directory structure
            for name in ("conf", "recipes"):
                path = os.path.join(layerpath, name)
                if not os.path.isdir(path):
                    os.makedirs(path)

            # create layer.oonf
            config = os.path.join(layerpath, "conf", "layer.conf")
            if not os.path.isfile(config):
                with open(config, "w") as conf:
                    conf.write('BBPATH .= ":${LAYERDIR}"\nBBFILES += "${LAYERDIR}/recipes/*.bb"\n')

            # Update the Layer_Version dirpath that has our base_recipe in
            # to be able to read the base recipe to then  generate the
            # custom recipe.
            br_layer_base_recipe = layers.get(
                layer_version=customrecipe.base_recipe.layer_version)

            br_layer_base_dirpath = \
                    os.path.join(self.be.sourcedir,
                                 self.getGitCloneDirectory(
                                     br_layer_base_recipe.giturl,
                                     br_layer_base_recipe.commit),
                                 customrecipe.base_recipe.layer_version.dirpath
                                )

            customrecipe.base_recipe.layer_version.dirpath = \
                         br_layer_base_dirpath

            customrecipe.base_recipe.layer_version.save()

            # create recipe
            recipe_path = \
                    os.path.join(layerpath, "recipes", "%s.bb" % target.target)
            with open(recipe_path, "w") as recipef:
                recipef.write(customrecipe.generate_recipe_file_contents())

            # Update the layer and recipe objects
            customrecipe.layer_version.dirpath = layerpath
            customrecipe.layer_version.save()

            customrecipe.file_path = recipe_path
            customrecipe.save()

            # create *Layer* objects needed for build machinery to work
            BRLayer.objects.get_or_create(req=target.req,
                                          name=layer.name,
                                          dirpath=layerpath,
                                          giturl="file://%s" % layerpath)
        if os.path.isdir(layerpath):
            layerlist.append(layerpath)

        self.islayerset = True
        layerlist.extend(nongitlayerlist)
        return layerlist

    def readServerLogFile(self):
        return open(os.path.join(self.be.builddir, "toaster_server.log"), "r").read()


    def triggerBuild(self, bitbake, layers, variables, targets, brbe):
        layers = self.setLayers(bitbake, layers, targets)

        # init build environment from the clone
        builddir = '%s-toaster-%d' % (self.be.builddir, bitbake.req.project.id)
        oe_init = os.path.join(self.pokydirname, 'oe-init-build-env')
        # init build environment
        self._shellcmd("bash -c 'source %s %s'" % (oe_init, builddir),
                       self.be.sourcedir)

        # update bblayers.conf
        bblconfpath = os.path.join(builddir, "conf/bblayers.conf")
        conflines = open(bblconfpath, "r").readlines()
        skip = False
        with open(bblconfpath, 'w') as bblayers:
            for line in conflines:
                if line.startswith("# line added by toaster"):
                    skip = True
                    continue
                if skip:
                    skip = False
                else:
                    bblayers.write(line)

            bblayers.write('# line added by toaster build control\n'
                           'BBLAYERS = "%s"' % ' '.join(layers))

        # write configuration file
        confpath = os.path.join(builddir, 'conf/toaster.conf')
        with open(confpath, 'w') as conf:
            for var in variables:
                conf.write('%s="%s"\n' % (var.name, var.value))
            conf.write('INHERIT+="toaster buildhistory"')

        # run bitbake server from the clone
        bitbake = os.path.join(self.pokydirname, 'bitbake', 'bin', 'bitbake')
        self._shellcmd('bash -c \"source %s %s; BITBAKE_UI="knotty" %s --read %s '
                       '--server-only -t xmlrpc -B 0.0.0.0:0\"' % (oe_init,
                       builddir, bitbake, confpath), self.be.sourcedir)

        # read port number from bitbake.lock
        self.be.bbport = ""
        bblock = os.path.join(builddir, 'bitbake.lock')
        with open(bblock) as fplock:
            for line in fplock:
                if ":" in line:
                    self.be.bbport = line.split(":")[-1].strip()
                    logger.debug("localhostbecontroller: bitbake port %s", self.be.bbport)
                    break

        if not self.be.bbport:
            raise BuildSetupException("localhostbecontroller: can't read bitbake port from %s" % bblock)

        self.be.bbaddress = "localhost"
        self.be.bbstate = BuildEnvironment.SERVER_STARTED
        self.be.lock = BuildEnvironment.LOCK_RUNNING
        self.be.save()

        bbtargets = ''
        for target in targets:
            task = target.task
            if task:
                if not task.startswith('do_'):
                    task = 'do_' + task
                task = ':%s' % task
            bbtargets += '%s%s ' % (target.target, task)

        # run build with local bitbake. stop the server after the build.
        log = os.path.join(builddir, 'toaster_ui.log')
        local_bitbake = os.path.join(os.path.dirname(os.getenv('BBBASEDIR')),
                                     'bitbake')
        self._shellcmd(['bash -c \"(TOASTER_BRBE="%s" BBSERVER="0.0.0.0:-1" '
                        '%s %s -u toasterui --token="" >>%s 2>&1;'
                        'BITBAKE_UI="knotty" BBSERVER=0.0.0.0:-1 %s -m)&\"' \
                        % (brbe, local_bitbake, bbtargets, log, bitbake)],
                        builddir, nowait=True)

        logger.debug('localhostbecontroller: Build launched, exiting. '
                     'Follow build logs at %s' % log)
