# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import re
import os
import sys

from PySide import QtGui
from PySide import QtCore

from hiero.core import nuke
from hiero.exporters import FnNukeShotExporter
from hiero.exporters import FnNukeShotExporterUI
from .collating_exporter import CollatedShotPreset

import tank
from .base import ShotgunHieroObjectBase


class ShotgunNukeShotExporterUI(ShotgunHieroObjectBase, FnNukeShotExporterUI.NukeShotExporterUI):
    """
    Custom Preferences UI for the shotgun nuke shot exporter
    """
    def __init__(self, preset):
        FnNukeShotExporterUI.NukeShotExporterUI.__init__(self, preset)
        self._displayName = "Shotgun Nuke Project File"
        self._taskType = ShotgunNukeShotExporter

    def populateUI(self, widget, exportTemplate):
        FnNukeShotExporterUI.NukeShotExporterUI.populateUI(self, widget, exportTemplate)

        layout = widget.layout()
        self._toolkit_list = QtGui.QListView()
        self._toolkit_list.setMinimumHeight(50)
        self._toolkit_list.resize(200, 50)

        self._toolkit_model = QtGui.QStandardItemModel()
        nodes = self.app.get_setting("nuke_script_toolkit_write_nodes")
        properties = self._preset.properties()

        for node in nodes:
            name = "Toolkit Node: %s (\"%s\")" % (node['name'], node['channel'])
            item = QtGui.QStandardItem(name)
            item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            if name in properties["toolkitWriteNodes"]:
                item.setData(QtCore.Qt.Checked, QtCore.Qt.CheckStateRole)
            else:
                item.setData(QtCore.Qt.Unchecked, QtCore.Qt.CheckStateRole)
            self._toolkit_model.appendRow(item)

        self._toolkit_list.setModel(self._toolkit_model)
        self._toolkit_model.dataChanged.connect(self.toolkitPresetChanged)

        layout.insertRow(0, "Shotgun Write Nodes:", self._toolkit_list)

    def toolkitPresetChanged(self, topLeft, bottomRight):
        self._preset.properties()["toolkitWriteNodes"] = []
        preset = self._preset.properties()["toolkitWriteNodes"]
        for row in xrange(0, self._toolkit_model.rowCount()):
            item = self._toolkit_model.item(row, 0)
            if item.data(QtCore.Qt.CheckStateRole) == QtCore.Qt.Checked:
                preset.append(item.text())

        self.app.log_debug("toolkitPresetChanged: %s" % preset)


class ShotgunNukeShotExporter(ShotgunHieroObjectBase, FnNukeShotExporter.NukeShotExporter):
    """
    Create Transcode object and send to Shotgun
    """
    def __init__(self, initDict):
        """
        Constructor
        """
        FnNukeShotExporter.NukeShotExporter.__init__(self, initDict)
        self._resolved_export_path = None
        self._tk_version_number = None
        self._thumbnail = None
        self._hero = None
        self._heroItem = None

        if self._collate:
            def keyFunc(item):
                return ((sys.maxint - item.timelineIn()) * 1000) + item.parent().trackIndex()
            heroItem = max(self._collatedItems, key=keyFunc)
            self._hero = (heroItem.guid() == self._item.guid())
            self._heroItem = heroItem

    def sequenceName(self):
        # override getSequence from the resolver to be collate friendly
        if getattr(self, '_collate', False):
            return self._item.parentSequence().name()
        return FnNukeShotExporter.NukeShotExporter.sequenceName(self)

    def taskStep(self):
        """
        Run Task
        """
        if self._resolved_export_path is None:
            self._resolved_export_path = self.resolvedExportPath()
            self._tk_version_number = self._formatTkVersionString(self.versionString())

            # convert slashes to native os style..
            self._resolved_export_path = self._resolved_export_path.replace("/", os.path.sep)


        source = self._item.source()
        self._thumbnail = source.thumbnail(source.posterFrame())
        
        return FnNukeShotExporter.NukeShotExporter.taskStep(self)

    def finishTask(self):
        """
        Finish Task
        """
        # run base class implementation
        FnNukeShotExporter.NukeShotExporter.finishTask(self)
        
        # Don't create PublishedFiles for non-hero collated items
        if self._collate and not self._hero:
            return

        # register publish
        # get context we're publishing to
        ctx = self.app.tank.context_from_path(self._resolved_export_path)
        published_file_type = self.app.get_setting('nuke_script_published_file_type')

        args = {
            "tk": self.app.tank,
            "context": ctx,
            "path": self._resolved_export_path,
            "name": os.path.basename(self._resolved_export_path),
            "version_number": int(self._tk_version_number),
            "published_file_type": published_file_type,
        }

        self.app.log_debug("Register publish in shotgun: %s" % str(args))
        sg_publish = tank.util.register_publish(**args)

        # upload thumbnail for sequence
        self._upload_thumbnail_to_sg(sg_publish, self._thumbnail)

    def _beforeNukeScriptWrite(self, script):
        """
        Add ShotgunWriteNodePlaceholder Metadata nodes for tk-nuke-writenode to 
        create full Tk WriteNodes in the Nuke environment
        """
        FnNukeShotExporter.NukeShotExporter._beforeNukeScriptWrite(self, script)

        for toolkit_specifier in self._preset.properties()["toolkitWriteNodes"]:
            # break down a string like 'Toolkit Node: Mono Dpx ("editorial")' into name and channel
            match = re.match("^Toolkit Node: (?P<name>.+) \(\"(?P<channel>.+)\"\)",
                toolkit_specifier)

            metadata = match.groupdict()
            node = nuke.MetadataNode(metadatavalues=metadata.items())
            node.setName('ShotgunWriteNodePlaceholder')

            self.app.log_debug("Created ShotgunWriteNodePlaceholder Node: %s" % node._knobValues)
            script.addNode(node)


class ShotgunNukeShotPreset(ShotgunHieroObjectBase, FnNukeShotExporter.NukeShotPreset, CollatedShotPreset):
    """
    Settings for the shotgun transcode step
    """

    def __init__(self, name, properties):
        FnNukeShotExporter.NukeShotPreset.__init__(self, name, properties)
        self._parentType = ShotgunNukeShotExporter
        CollatedShotPreset.__init__(self, self.properties())
        
        if "toolkitWriteNodes" in properties:
            # already taken care of by loading the preset
            return

        # default toolkit write nodes
        toolkit_write_nodes = []
        nodes = self.app.get_setting("nuke_script_toolkit_write_nodes")
        for node in nodes:
            name = "Toolkit Node: %s (\"%s\")" % (node['name'], node['channel'])
            toolkit_write_nodes.append(name)
        self.properties()["toolkitWriteNodes"] = toolkit_write_nodes
