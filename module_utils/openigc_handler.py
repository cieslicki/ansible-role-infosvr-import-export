###
# Copyright 2018 IBM Corp. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
###
"""
This module adds generic utility functions for interacting with Information Analyzer XML files
"""

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from lxml import etree
import re


ns = {
    'x': 'http://www.ibm.com/iis/flow-doc'
}
# Note we exlude TZ offset as this isn't supported on Python 2 without a non-standard library
t_format = "%Y-%m-%dT%H:%M:%S"


class OpenIGCHandler(object):
    def __init__(self, module, result, oigcfile):
        self.module = module
        self.result = result
        self.tree = etree.parse(oigcfile)
        for key in ns:
            etree.register_namespace(key, ns[key])
        self.root = self.tree.getroot()

    def getAssets(self):
        return self.root.xpath("./x:assets/x:asset", namespaces=ns)

    def getRid(self, e_asset):
        # Trim off the 'ID_' portion of the id to get the rid
        return e_asset.xpath("./@ID", namespaces=ns)[0][3:]

    def getAssetById(self, rid):
        asset_list = self.root.xpath("./x:assets/x:asset[@ID='ID_" + rid + "']", namespaces=ns)
        if len(asset_list) == 1:
            return asset_list[0]
        elif len(asset_list) > 1:
            self.module.warn("Multiple assets with same RID found: " + rid)
            return asset_list[0]
        else:
            self.module.warn("Asset not found with RID: " + rid)
            return None

    def getReferencedAsset(self, e_asset):
        e_ref = e_asset.xpath("./x:reference", namespaces=ns)
        asset_ids = None
        if len(e_ref) == 1:
            asset_ids = e_ref[0].xpath("./@assetIDs", namespaces=ns)[0]
        elif len(e_ref) > 1:
            self.module.warn("Multiple references found for: " + self.getRid(e_asset))
            asset_ids = e_ref[0].xpath("./@assetIDs", namespaces=ns)[0]
        if asset_ids is not None:
            return self.getAssetById(asset_ids[3:])
        else:
            return None

    def getAncestralAssetRids(self, rid):
        e_asset = self.getAssetById(rid)
        if e_asset is not None:
            e_parent = self.getReferencedAsset(e_asset)
            if e_parent:
                parent_rid = self.getRid(e_parent)
                return self.getAncestralAssetRids(parent_rid).append(parent_rid)
            else:
                return []
        else:
            return []

    def getAssetChildrenRids(self, rid):
        a_references = []
        references = self.root.xpath("./x:assets/x:asset/x:reference[@assetIDs='ID_" + rid + "']", namespaces=ns)
        for reference in references:
            a_references.append(self.getRid(reference.getparent()))
        return a_references

    def getImportActions(self):
        e_importAction = self.root.xpath("./x:importAction", namespaces=ns)
        return e_importAction[0].xpath("./@partialAssetIDs", namespaces=ns)[0].split(" ")

    def setImportActionPartials(self, asset_rids):
        e_importAction = self.root.xpath("./x:importAction", namespaces=ns)
        e_importAction[0].set("partialAssetIDs", " ID_".join(asset_rids))

    def dropAsset(self, e_asset):
        parent = e_asset.getparent()
        parent.remove(e_asset)
        self.result['changed'] = True

    def writeCustomizedXML(self, filename):
        return self.tree.write(filename, encoding='UTF-8', xml_declaration=True)

    def getCustomizedXMLAsString(self):
        return etree.tostring(self.root, encoding='UTF-8', xml_declaration=True)
