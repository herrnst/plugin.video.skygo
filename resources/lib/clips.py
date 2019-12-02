#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import json
import time
import base64
# cryptopy
from crypto.cipher import aes_cbc


class Clips:

    secret_key = 'XABD-FHIM-GDFZ-OBDA-URDG-TTRI'
    aes_key = ['826cf604accd0e9d61c4aa03b7d7c890', 'da1553b1515bd6f5f48e250a2074d30c']


    def __init__(self, skygo):

        self.skygo = skygo


    def getClipToken(self, content):
        clipType = 'FREE'
        if content == 'ENTITLED USER' or content == 'SUBSCRIBED USER':
            clipType = 'NOTFREE'
        timestamp = str(time.time()).replace('.', '')
        url = 'https://www.skygo.sky.de/SILK/services/public/clipToken?clipType={0}&product=SG&platform=web&version=12354=&_{1}'.format(clipType, timestamp)
        r = self.skygo.session.get(url)
        if common.get_dict_value(r.headers, 'content-type').startswith('application/json'):
            return json.loads(r.text[3:len(r.text) - 1])
        else:
            None


    def buildClipUrl(self, url, token):
        # pyCrypto
        # dec = AES.new(self.aes_key[0].decode('hex'), AES.MODE_CBC, self.aes_key[1].decode('hex'))
        # path = dec.decrypt(base64.b64decode(token['tokenValue']))
        # query = '{0}={1}'.format(token['tokenName'], path2[0:len(path2)-7])
        #
        # cryptopy
        dec = aes_cbc.AES_CBC(key=self.aes_key[0].decode('hex'), keySize=16)
        path = dec.decrypt(base64.b64decode(token['tokenValue']), iv=self.aes_key[1].decode('hex'))
        query = '{0}={1}'.format(token['tokenName'], path)
        return '{0}?{1}'.format(url, query)


    def playClip(self, clip_id):
        if self.skygo.login():
            clip_info = self.skygo.getClipDetails(clip_id)
            token = getClipToken(clip_info['content_subscription'])
            manifest = buildClipUrl(clip_info['videoUrlMSSProtected'], token)

            self.skygo.play(manifest, clip_info['package_code'])