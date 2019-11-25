#!/usr/bin/env python
# -*- coding: utf-8 -*-

import xbmcaddon
import ast
from collections import OrderedDict

try:
    import urllib.parse as urllib
except:
    import urllib

base_url = "plugin://" + xbmcaddon.Addon().getAddonInfo('id')


def build_url(query):
    query.update({'zz': ''})
    query = OrderedDict(query.items())
    return base_url + '?' + urllib.urlencode(query)


def getDictFromString(str):
    return ast.literal_eval(str) if str else None


def get_dict_value(dict, key):
    key = key.lower()
    result = [dict[k] for k in dict if k.lower() == key]
    return result[0] if len(result) > 0 else ''