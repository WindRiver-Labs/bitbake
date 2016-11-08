# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models

### WIND_RIVER_EXTENSION_BEGIN ###
class Migration(migrations.Migration):

    dependencies = [
        ('orm', '0015_layer_local_source_dir'),
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
            name='WRDistro',
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
    ]
### WIND_RIVER_EXTENSION_END ###

