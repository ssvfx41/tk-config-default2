# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Hook that gets executed every time an engine has fully initialized.

"""
import os
import sgtk
import sys


try:
    from ss_config.hooks.core.engine_init import SsEngineInit

except ImportError:
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

    from ss_config.hooks.core.engine_init import SsEngineInit


class EngineInit(SsEngineInit):
    """
    Gets executed when a Toolkit engine has fully initialized.
    At this point, all applications and frameworks have been loaded,
    and the engine is fully operational.
    """
    pass
