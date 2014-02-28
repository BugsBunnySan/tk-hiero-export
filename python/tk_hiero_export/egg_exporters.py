import os.path

from PySide import QtCore
from PySide import QtGui

import sgtk

import hiero.ui
import hiero.core
from hiero.exporters import FnAudioExportUI, FnAudioExportTask

from .base import ShotgunHieroObjectBase

__all__ = ['ShotgunAudioExportUI', 'ShotgunAudioExportTask', 'ShotgunAudioExportPreset']

# shotgun publishing audio exporter

class ShotgunAudioExportUI(ShotgunHieroObjectBase, FnAudioExportUI.AudioExportUI):
    def __init__(self, preset):
        FnAudioExportUI.AudioExportUI.__init__(self, preset)
        self._displayName = "Shotgun Audio Exporter"
        self._taskType = ShotgunAudioExportTask
    
    def populateUI(self, widget, exportTemplate):
        layout = QtGui.QVBoxLayout(widget)
        top = QtGui.QWidget()
        middle = QtGui.QWidget()
        layout.addWidget(top)
        layout.addWidget(middle)

        voiceCheckboxToolTip = 'When enabled, export audio as the voice track'
        voiceCheckbox = QtGui.QCheckBox()
        voiceCheckbox.setToolTip(voiceCheckboxToolTip)
        voiceCheckbox.stateChanged.connect(self._voiceCheckboxClicked)
        if self._preset.properties()['voiceEnabled']:
            voiceCheckbox.setCheckState(QtCore.Qt.Checked)

        vc_layout = QtGui.QFormLayout(top)
        vc_layout.addRow('Voice Track', voiceCheckbox)

        FnAudioExportUI.AudioExportUI.populateUI(self, middle, exportTemplate)        

    def _voiceCheckboxClicked(self, state):
        self._preset.properties()['voiceEnabled'] = state == QtCore.Qt.Checked

class ShotgunAudioExportTask(ShotgunHieroObjectBase, FnAudioExportTask.AudioExportTask):
    def __init__(self, initDict):
        FnAudioExportTask.AudioExportTask.__init__(self, initDict)
        self._resolved_export_path = None
        self._sequence_name        = None
        self._shot_name            = None

    def resolveNames(self):
        if self._resolved_export_path is None:
            self._resolved_export_path = self.resolvedExportPath()
            self._tk_version = self._formatTkVersionString(self.versionString())
            self._sequence_name = self.sequenceName()

            # convert slashes to native os style..
            self._resolved_export_path = self._resolved_export_path.replace("/", os.path.sep)

            self._shot_name = self.shotName()

            source = self._item.source()

    def taskStep(self):
        if not isinstance(self._item, hiero.core.TrackItem) or not self._sequenceHasAudio(self._sequence):
            self._finished = True
            return False

        # well, wouldn't it have been nice if the following actually did something??
        #prj = self._project
        #audio_tracks = prj.audioTracks()

        #print prj
        #print audio_tracks

        #for track in audio_tracks:
        #    print 'processing track %s' % track.name()
        #    if track.name() == 'voice' and self._preset.properties()['voiceEnabled']:
        #        hiero.core.executeInMainThreadWithResult(hiero.core.TrackBase.setEnabled, track, True)
        #        print track.isEnabled()
        #    elif track.name() == 'sfx' and not self._preset.properties()['voiceEnabled']:
        #        hiero.core.executeInMainThreadWithResult(hiero.core.TrackBase.setEnabled, track, True)
        #        print track.isEnabled()
        #    else:
        #        hiero.core.executeInMainThreadWithResult(hiero.core.TrackBase.setEnabled, track, False)
        #        print track.isEnabled()

        FnAudioExportTask.AudioExportTask.taskStep(self)
        self.resolveNames()
        self._finished = False
        return False

    def finishTask(self):
        FnAudioExportTask.AudioExportTask.finishTask(self)
            
        sg = self.app.shotgun
        # lookup current login
        sg_current_user = sgtk.util.get_current_user(self.app.tank)
        # lookup sequence
        
        sg_sequence = sg.find_one("Sequence",
                                  [["project", "is", self.app.context.project],
                                   ["code", "is", self._sequence_name]])
        sg_shot = None
        if sg_sequence:
            sg_shot = sg.find_one("Shot", [["sg_sequence", "is", sg_sequence], ["code", "is", self._shot_name]])
            if sg_shot:
                # create publish
                ################
                # by using entity instead of export path to get context, this ensures 
                # collated plates get linked to the hero shot
                ctx = self.app.tank.context_from_entity('Shot', sg_shot['id'])
                published_file_type = self.app.get_setting('audio_published_file_type')
                
                if self._preset.properties()['voiceEnabled']:
                    description = 'voice'
                else:
                    description = 'sfx'

                args = {
                    "tk": self.app.tank,
                    "context": ctx,
                    "path": self._resolved_export_path,
                    "name": os.path.basename(self._resolved_export_path),
                    "version_number": int(self._tk_version),
                    "published_file_type": published_file_type,
                    "comment": description, # "a string containing a description of the comment" ?? shotgun, go home, you're drunk
                }

                # register publish;
                self.app.log_debug("Register publish in shotgun: %s" % str(args))
                pub_data = sgtk.util.register_publish(**args)
            

class ShotgunAudioExportPreset(ShotgunHieroObjectBase, FnAudioExportTask.AudioExportPreset):
    def __init__(self, name, properties):
        FnAudioExportTask.AudioExportPreset.__init__(self, name, properties)
        self._parentType = ShotgunAudioExportTask
        if 'voiceEnabled' not in self.properties():
            self.properties()['voiceEnabled'] = False

    def addUserResolveEntries(self, resolver):
        self.app.log_debug('Adding audio type resolver')
        resolver.addResolver("{audio_type}", "AudioType",
                             lambda keyword, task: self._formatAudioTypeString(keyword, task))

    def _formatAudioTypeString(self, keyword, task):
        if self.properties()['voiceEnabled']:
            return 'voice'
        else:
            return 'sfx'
