# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

### THIS MUST BE LOCAL IN ALL CONFIGS TO UPDATE ENVIRONMENT ###
# TODO: Centralize this in the same way in before_app_launch.py.

import os
import sys
import sgtk

roots = [os.getenv("SSVFX_PIPELINE_DEV"), os.getenv("SSVFX_PIPELINE")]
if not any(roots):
    if sys.platform.startswith("win"):
        local_pipe = "\\\\ssvfx_pipeline\\pipeline_repo"
    else:
        local_pipe = "/mnt/pipeline_repo"

    roots.append(local_pipe)
    os.environ["SSVFX_PIPELINE"] = local_pipe

for root_path in roots:
    if not root_path:
        continue

    test_env = os.getenv("TEST_ENV", False)
    if not test_env:
        source_root = "master"
    else:
        source_root = "testEnv"

    sg_path = os.path.join(root_path, source_root, "ssvfx_sg")
    if os.path.exists(sg_path):
        sys.path.append(os.path.normpath(sg_path))
        break

from ss_config.hooks.tk_multi_publish2.desktop.pre_publish import SsPrePublishHook

HookBaseClass = sgtk.get_hook_baseclass()


class PrePublishHook(SsPrePublishHook):
    """
    This hook defines logic to be executed before showing the publish
    dialog. There may be conditions that need to be checked before allowing
    the user to proceed to publishing.
    """
    pass
