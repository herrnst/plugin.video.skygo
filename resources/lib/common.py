#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import xbmcaddon
import ast
from collections import OrderedDict

try:
    from urllib.parse import urlencode
except:
    from urllib import urlencode


class Common:


    def __init__(self, addon, addon_handle):

        self.addon = addon
        self.addon_handle = addon_handle

        self.base_url = 'plugin://{0}'.format(self.addon.getAddonInfo('id'))


    def build_url(self, query):
        query.update({'zz': ''})
        query = OrderedDict(query.items())
        return '{0}?{1}'.format(self.base_url, urlencode(query))


    def getDictFromString(self, str):
        return ast.literal_eval(str) if str else None


    def get_dict_value(self, dict, key):
        key = key.lower()
        result = [dict[k] for k in dict if k.lower() == key]
        return result[0] if len(result) > 0 else ''