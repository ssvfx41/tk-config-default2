# Copyright (c) 2017 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

# ### OVERRIDDEN IN SSVFX_SG ###
from ss_config.hooks.tk_multi_publish2.outsource.outsource_publish_file import SsOutsourceFilePublishPlugin

class BasicFilePublishPlugin(SsOutsourceFilePublishPlugin):
    """
    Hook called to perform an operation with the
    current scene
    """
    pass