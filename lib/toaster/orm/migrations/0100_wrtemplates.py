# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models

### WIND_RIVER_EXTENSION_BEGIN ###
class Migration(migrations.Migration):

    dependencies = [
        ('orm', '0016_clone_progress'),
    ]

    operations = [
        migrations.CreateModel(
            name='WRTemplate',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('up_id', models.IntegerField(default=None, null=True)),
                ('up_date', models.DateTimeField(default=None, null=True)),
                ('name', models.CharField(max_length=255)),
                ('description', models.CharField(max_length=255)),
                ('layer_version', models.ForeignKey(to='orm.Layer_Version')),
            ],
        ),
        migrations.CreateModel(
            name='Distro',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('up_id', models.IntegerField(default=None, null=True)),
                ('up_date', models.DateTimeField(default=None, null=True)),
                ('name', models.CharField(max_length=255)),
                ('description', models.CharField(max_length=255)),
                ('layer_version', models.ForeignKey(to='orm.Layer_Version')),
            ],
        ),
        migrations.CreateModel(
            name='ProjectTemplate',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('project', models.ForeignKey(to='orm.Project')),
                ('wrtemplate', models.ForeignKey(to='orm.WRTemplate')),
            ],
        ),
        migrations.CreateModel(
            name='BuildTemplate',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('build', models.ForeignKey(related_name='wrtemplate_build', default=None, to='orm.Build', null=True)),
                ('wrtemplate', models.ForeignKey(to='orm.WRTemplate')),
            ],
        ),
        migrations.AddField(
            model_name='build',
            name='kernel',
            field=models.TextField(null=True, default=None),
        ),
    ]
### WIND_RIVER_EXTENSION_END ###

