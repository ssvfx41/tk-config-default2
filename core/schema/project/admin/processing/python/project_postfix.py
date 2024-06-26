import argparse
import json
import os
import sys

# Add ssvfx_scripts to env if not already there
if "SSVFX_PIPELINE" not in os.environ.keys():
    error = "ERROR! Missing SSVFX_PIPELINE Environment variable! Aborting."
    print(error)
    raise ImportError(error)

dev_root = os.environ.get("SSVFX_PIPELINE_DEV", "")
if os.path.exists(dev_root):
    pipeline_root = dev_root
else:
    pipeline_root = os.environ["SSVFX_PIPELINE"]

repos = ["ssvfx_scripts", "ssvfx_sg"]
for repo in repos:
    repo_path = os.path.join(pipeline_root, "master", repo)
    if not os.path.exists(repo_path):
        repo_path = os.path.join(pipeline_root, repo)

    if repo_path not in sys.path:
        sys.path.append(repo_path)
        print(
            "Added {repo} path to environment: {path}".format(repo=repo, path=repo_path)
        )

from sgpy.sg_tools import sg_connection
from general import basic_utils
from general.file_functions import json_reader

logger = basic_utils.get_logger(__name__)

logger.info("Python Version: {}".format(sys.version))
logger.info("----------------------------------\n")


def dict_nav(dictionary, sequence):
    """
    Simplified navigator for nested dictionaries
    returns first non-dictionary value or None

    :dictionary: starting dictionary to navifate
    :sequence: ordered sequence of keys to test in list form
    """
    if not dictionary or not sequence:
        return None

    logger.info(">>>>> Navigating sub-dictionaries for: %s" % "->".join(sequence))
    sub_dict = dictionary
    for key in sequence:
        sub_dict = sub_dict.get(key)

        if key == sequence[-1]:
            return sub_dict

        if not isinstance(sub_dict, dict):
            return sub_dict


def swap_paths(json_data):
    """
    Recursive function for correcting paths from the input json data.
    Args:
        json_data(dict): Json file data that is being processed.

    Returns: Nothing, updates json data to sanitize paths.

    """
    for key, value in json_data.items():
        # recursively fix paths in dictionaries
        if isinstance(value, dict):
            swap_paths(value)
            continue

        if not isinstance(value, str):
            continue

        if value.startswith("\\\\") or value.startswith("//") or value.startswith("/mnt"):
            new_value = os.path.abspath(basic_utils.swap_render_path_root(value))
            json_data[key] = new_value
            logger.info(value)
            logger.info(json_data[key])
            logger.info("==============")


def run_post_fix(json_filepath):
    """
    Default project post-fix process
    Args:
        json_filepath: Full path to a valid pump json file.

    Returns: 0 if process completes without errors.

    """
    logger.info("Loading json data...")
    with open(json_filepath, "r") as file_read:
        json_data = json_reader.json_load_version_check(file_read)

    logger.info("Loaded Json data successfully.")
    logger.info("---")

    logger.info("-----------------------------")
    logger.info("Updating paths for Windows...")
    logger.info("==============")
    swap_paths(json_data)
    logger.info("==============")
    logger.info("Update complete.")
    logger.info("-----------------------------")

    # Get shared variables from entity_info
    seq_ccc_path = dict_nav(
        json_data,
        [
            "entity_info",
            "sg_seq_ccc",
            "local_path_windows",
        ],
    )

    first_frame = str(dict_nav(json_data, ["entity_info", "sg_head_in"]))
    last_frame = str(dict_nav(json_data, ["entity_info", "sg_tail_out"]))

    ############################
    # ## Shotgrid Tag Query ## #
    ############################
    entity_info = json_data["entity_info"]
    entity_type = entity_info["type"]
    entity_id = entity_info["id"]

    sg = sg_connection.sg_connect()
    entity = sg.find_one(
        entity_type=entity_type, filters=[["id", "is", int(entity_id)]], fields=["tags"]
    )

    color_switch_2 = False

    # tag name: color_switch 2
    color_switch_2_tag_id = 5415
    if entity:
        tag_ids = [tag["id"] for tag in entity["tags"]]
        if color_switch_2_tag_id in tag_ids:
            color_switch_2 = True
            logger.info("Got color_switch 2 tag! Setting color switch to 2.")

    processes = json_data["processes"]
    if not processes:
        logger.warning("Warning there are no processes to loop!")

    # Version status
    version_info = json_data.get("version_info") or {}
    version_status = version_info.get("sg_status_list") or ""

    # Artist
    if version_info.get("relationships"):
        user = version_info["relationships"].get("user") or {}
        if user.get("data"):
            user_login = None
            user_name = user["data"]["name"]
        else:
            user_login = json_data["project_info"]["user"]
            user_name = None
    else:
        user_login = json_data["project_info"]["user"]
        user_name = None

    if user_login and not user_name:
        user_ent = sg.find_one(
            entity_type="HumanUser",
            filters=[["login", "is", user_login]],
            fields=["name"],
        )
        if user_ent:
            user_name = user_ent["name"]
        else:
            user_name = ""

    # Corrective Loop to add nuke node values to JSON file
    total = len(processes.keys())
    count = 0
    for job_key, job_data in processes.items():
        count += 1
        logger.info("***********************")
        logger.info(
            "{count} of {total} - {job_key}".format(
                count=count, total=total, job_key=job_key
            )
        )
        logger.info("***********************")

        # check for nuke settings, Entity info, sequence ccc info, and sequence ccc path
        # if all are present, generate node dictionary and save the json
        nuke_settings = job_data.get("nuke_settings")
        if not nuke_settings:
            logger.info(">>>>> No Nuke Settings, bypassing: %s" % job_key)
            continue

        proc_settings = job_data.get("process_settings")
        if not proc_settings:
            logger.info(">>>>> No Process Settings, bypassing: %s" % job_key)
            continue

        #####################
        # ## Color Fixes ## #
        #####################
        if proc_settings.get("color_required"):
            if seq_ccc_path:
                nuke_settings["seq_ccc"] = {
                    "read_from_file": True,
                    "file": seq_ccc_path.replace("\\", "/"),
                    "disable": False,
                }
                logger.info(
                    ">>>>> Found Sequence CCC Path: %s\n" % nuke_settings.get("seq_ccc")
                )
            else:
                nuke_settings["seq_ccc"] = {"disable": True}

            if not nuke_settings.get("shot_ccc"):
                nuke_settings["shot_ccc"] = {"disable": True}

            if not nuke_settings.get("shot_lut"):
                nuke_settings["shot_lut"] = {"disable": True}

        #####################
        # ## Slate Fixes ## #
        #####################
        # Fix any silly filename/version name connections
        slate = nuke_settings.get("SSVFX_SLATE")
        if slate:
            # fix version name
            reset_version = slate.get("version")
            if reset_version:
                slate.update({"version": reset_version.split("/")[-1]})

            if first_frame and last_frame:
                slate.update(
                    {
                        "start_frame": float(first_frame),
                        "end_frame": float(last_frame),
                    }
                )

            slate["artist"] = user_name
            logger.info(">>>>> Updated Slate Node: %s" % slate)

        ##############################
        # Version Zero Thumbnail Fix #
        ##############################
        # If version status is zerov, update thumbnail media on linked version.
        if job_key in ["version_zero_thumbnail"]:
            if version_status and version_status in ["zerov"]:
                proc_settings["update_version_media"] = True
                logger.info(
                    ">>>>> Got Version Zero, setting update_version_media to True."
                )

        #####################
        # ## Tag changes ## #
        #####################
        if job_key == "client-version-dnxhd":
            if color_switch_2:
                logger.info(">>>>> Setting color_switch to 2")
                nuke_settings["color_switch"] = {"which": 2}
                logger.info(">>>>> color_switch: %s" % nuke_settings["color_switch"])

    logger.info("---")
    logger.info(">>>>> Completed Postfix Process, writing json...")

    # re-write JSON file
    json_object = json.dumps(json_data, indent=4)
    with open(json_filepath, "w") as outfile:
        outfile.write(json_object)
        outfile.close()

    logger.info(">>>>> Postfix JSON write complete. Resuming pump_process.py")
    return 0


def get_parser():
    """
    Get argument parser for Pump project post-fix.
    Returns: argparse.ArgumentParser object
    """
    parser = argparse.ArgumentParser(
        prog="pump_project_postfix",
        description="Runs the generic project post-fix process.",
    )
    parser.add_argument("json_filepath", help="Path to the submitted .json file.")
    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()

    json_filepath = args.json_filepath
    logger.info("ARGS: json_filepath: {}\n".format(json_filepath))
    if not os.path.exists(json_filepath):
        _error = "ERROR! Json Filepath does not exist! Cannot continue, exiting. Filepath: {}".format(
            json_filepath
        )
        logger.error(_error)
        return _error

    result = run_post_fix(json_filepath)
    return result


if __name__ == "__main__":
    sys.exit(main())
