from tank import Hook

class HieroResolveCustomStrings(Hook):
    _sg_lookup_cache = {'Sequence': {},
                        'Scene'   : {},
                        'Shot'    : {}}

    def _formatSequenceString(self, keyword, task, sg_shot):
        sg_sequence = None
        if sg_shot['sg_sequence']['id'] not in HieroResolveCustomStrings._sg_lookup_cache['Sequence']:
            sg_sequence = self.parent.shotgun.find_one('Sequence', [['id', 'is', sg_shot['sg_sequence']['id']]], fields=['code'])
            if not sg_sequence:
                return ''
            HieroResolveCustomStrings._sg_lookup_cache['Sequence'][sg_shot['sg_sequence']['id']] = sg_sequence
        else:
            sg_sequence = HieroResolveCustomStrings._sg_lookup_cache['Sequence'][sg_shot['sg_sequence']['id']]
        return sg_sequence['code']
        
    def _formatSceneString(self, keyword, task, sg_shot):
        sg_scene = None
        if sg_shot['sg_scene']['id'] not in HieroResolveCustomStrings._sg_lookup_cache['Scene']:
            sg_scene = self.parent.shotgun.find_one('Scene', [['id', 'is', sg_shot['sg_scene']['id']]], fields=['code'])
            if not sg_scene:
                return ''
            HieroResolveCustomStrings._sg_lookup_cache['Scene'][sg_shot['sg_scene']['id']] = sg_scene
        else:
            sg_scene = HieroResolveCustomStrings._sg_lookup_cache['Scene'][sg_shot['sg_scene']['id']]
        return sg_scene['code']        

    def _formatShotNoString(self, keyword, task, sg_shot):
        return sg_shot['sg_shot_no']


    def execute(self, task, keyword, **kwargs):
        lookup_key = task._item.name()
        if lookup_key in HieroResolveCustomStrings._sg_lookup_cache['Shot']:
            sg_shot = HieroResolveCustomStrings._sg_lookup_cache['Shot'][lookup_key]
        else:
            sg_shot = self.parent.shotgun.find_one("Shot", [['code', 'is', task._item.name()]], self.parent.get_setting("custom_template_fields"))
            HieroResolveCustomStrings._sg_lookup_cache['Shot'][lookup_key] = sg_shot
        if not sg_shot:
            return ''            
        if keyword == '{sg_sequence}':
            return self._formatSequenceString(keyword, task, sg_shot)
        elif keyword == '{sg_scene}':
            return self._formatSceneString(keyword, task, sg_shot)
        elif keyword == '{sg_shot_no}':
            return self._formatShotNoString(keyword, task, sg_shot)
        else:
            return ''
