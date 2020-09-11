# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.
import os
import sgtk
import shutil
import base64

HookBaseClass = sgtk.get_hook_baseclass()


class UploadVersionPlugin(HookBaseClass):
    """
    Plugin for sending quicktimes and images to shotgun for review.
    """

    @property
    def icon(self):
        """
        Path to an png icon on disk
        """

        if hasattr(self, "plugin_icon"):
            return self.plugin_icon

        # look for icon one level up from this hook's folder in "icons" folder
        return os.path.join(
            self.disk_location,
            "icons",
            "review.png"
        )

    @property
    def settings(self):
        """
        Dictionary defining the settings that this plugin expects to recieve
        through the settings parameter in the accept, validate, publish and
        finalize methods.

        A dictionary on the following form::

            {
                "Settings Name": {
                    "type": "settings_type",
                    "default": "default_value",
                    "description": "One line description of the setting"
            }

        The type string should be one of the data types that toolkit accepts as
        part of its environment configuration.
        """
        # inherit the settings from the base publish plugin
        base_settings = super(UploadVersionPlugin, self).settings or {}

        # settings specific to this class
        upload_version_settings = {
            "3D Version": {
                "type": "bool",
                "default": True,
                "description": "Generate a 3D Version instead of a 2D one?",
            },
            "Translation Worker": {
                "type": "str",
                "default": "local",
                "description": "Use local libraries or Forge Cloud Services for translations."
            },
            "Upload": {
                "type": "bool",
                "default": False,
                "description": "Upload content to Shotgun?"
            },
        }

        # update the base settings
        base_settings.update(upload_version_settings)

        return base_settings

    @property
    def item_filters(self):
        """
        List of item types that this plugin is interested in.

        Only items matching entries in this list will be presented to the
        accept() method. Strings can contain glob patters such as *, for example
        ["maya.*", "file.maya"]
        """
        return [
            "file.alias",
            "file.vred",
            "file.catpart",
            "file.igs",
            "file.jt",
            "file.stp",
            "file.motionbuilder"
        ]

    def accept(self, settings, item):
        """
        Method called by the publisher to determine if an item is of any
        interest to this plugin. Only items matching the filters defined via the
        item_filters property will be presented to this method.

        A publish task will be generated for each item accepted here. Returns a
        dictionary with the following booleans:

            - accepted: Indicates if the plugin is interested in this value at
                all. Required.
            - enabled: If True, the plugin will be enabled in the UI, otherwise
                it will be disabled. Optional, True by default.
            - visible: If True, the plugin will be visible in the UI, otherwise
                it will be hidden. Optional, True by default.
            - checked: If True, the plugin will be checked in the UI, otherwise
                it will be unchecked. Optional, True by default.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process

        :returns: dictionary with boolean keys accepted, required and enabled
        """

        if settings.get("3D Version").value is True:
            self.plugin_icon = os.path.join(
                self.disk_location,
                "icons",
                "3d_model.png"
            )
        
        if settings.get("Translation Worker").value == "local":
            self.logger.debug("Using local libraries for translation")
        elif settings.get("Translation Worker").value == "forge":
            self.logger.debug("Using Forge Cloud Services for translation")
        else:
            self.logger.error("Unknown Translation Worker")

        return {"accepted": True, "checked": True}

    def validate(self, settings, item):
        """
        Validates the given item to check that it is ok to publish. Returns a
        boolean to indicate validity.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        :returns: True if item is valid, False otherwise.
        """

        framework_lmv = self.load_framework("tk-framework-lmv_v0.1.x")
        if not framework_lmv:
            self.logger.error(
                "Could not run LMV translation: missing ATF framework"
            )
            return False
        
        framework_forge = self.load_framework("tk-framework-forge_v0.1.x")
        if not framework_forge:
            self.logger.error(
                "Could not load Forge framework"
            )
            return False

        self.logger.debug("translation worker {}".format(settings.get("Translation Worker").value))

        return True

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.
        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """

        # create the Version in Shotgun
        super(UploadVersionPlugin, self).publish(settings, item)


        # generate the Version content: LMV file or simple 2D thumbnail
        if settings.get("3D Version").value is True:
            self.logger.debug("Creating LMV files from source file")

            if settings.get("Translation Worker").value == "local":
                # translate the file to lmv and upload the corresponding package to the Version
                package_path, thumbnail_path, output_directory = self._translate_file_to_lmv(item)

                self.logger.debug("Translation package path {}".format(package_path))
                self.logger.debug("Translation thumbnail path {}".format(thumbnail_path))

                self.logger.debug("Uploading LMV file to Shotgun")
                self.logger.debug("parent {}, shotgun {}".format(self.parent, self.parent.shotgun))
                self.parent.shotgun.upload(
                    entity_type="Version",
                    entity_id=item.properties["sg_version_data"]["id"],
                    path=package_path,
                    field_name="sg_uploaded_movie"
                    # field_name="sg_translation_files"
                )
                self.parent.shotgun.update(
                    entity_type="Version",
                    entity_id=item.properties["sg_version_data"]["id"],
                    data={
                        "sg_translation_type": "LMV"
                    }
                )
                # if the Version thumbnail is empty, update it with the newly created thumbnail
                if not item.get_thumbnail_as_path() and thumbnail_path:
                    self.parent.shotgun.upload_thumbnail(
                        entity_type="Version",
                        entity_id=item.properties["sg_version_data"]["id"],
                        path=thumbnail_path
                    )
                # delete the temporary folder on disk
                self.logger.debug("Deleting temporary folder")
                shutil.rmtree(output_directory)
            
            else:
                # Use Forge Cloud Services for translation
                #
                # 1. set up http client and forge app credentials
                #>>>>>will need to create an official forge app and store credentials better
                #>>>>>http ... ok to use the tank_vendor HTTP class or should we use the forge python client?
                # 2. authenticate with forge
                # 3. create bucket for upload
                #>>>>>how to choose bucket? is there a bucket that current is being used?
                # 4. upload files to OSS
                #>>>>>need to use the 'resumable' endpoint for files >100MB
                # 5. kick off translation job
                # 6. check manifest for status
                #>>>>>this is what takes the longest -- don't need to wait for it since we already have the urn but on failure?
                # 7. update the version fields?
                #>>>>>add urn field? do we still need to upload the zip folder? (how to get the zip?)
                # 8. if no version thumbnail, update it with the created thumbnail
                #>>>>>translation job sent to do thumbnails but how to get them after and what to do with them?

                ### DEBUG
                # import sys
                # sys.path.append("/Users/oues/python_libs")
                # import ptvsd
                # ptvsd.enable_attach(redirect_output=True)
                # ptvsd.wait_for_attach()
                ### END DEBUG

                framework_forge = self.load_framework("tk-framework-forge_v0.1.x")
                if not framework_forge:
                    self.logger.error(
                        "Could not load Forge framework"
                    )

                self.logger.debug("Forge framework {}".format(framework_forge))
                
                forge_api = framework_forge.import_module("forge_api")
                forge_client = forge_api.ForgeClient()
                forge_client._authenticate()
                forge_client._create_bucket()
                upload_data = forge_client.upload_file(item.properties.path, item.name)

                # Should we use tank_endor representer.py instead?
                urn = base64.urlsafe_b64encode(bytes(upload_data["objectId"].rstrip('=')))
                self.logger.debug("base64 url safe {}".format(urn))
                name = upload_data["objectKey"]
                result = forge_client.post_job(urn, name)

                # TODO: make this op async, or return right away since we don't really need to wait for the job complete,
                # we already have the urn, but we would need to update the status once complete
                job_finished = False
                manifest = None
                while not job_finished:
                    manifest = forge_client.get_manifest(result["urn"])
                    job_finished = manifest["status"] != "pending" and manifest["status"] != "inprogress"
                
                if manifest and manifest["status"] == "success":
                    self.parent.shotgun.update(
                        entity_type="Version",
                        entity_id=item.properties["sg_version_data"]["id"],
                        data={
                            "sg_urn": manifest["urn"]
                        }
                    )
                else:
                    self.logger.error("Forge Cloud Translation -- manifest failed")
                
                forge_client._close_connection()

        else:
            # 3D Version = False

            thumbnail_path = item.get_thumbnail_as_path()
            self.logger.debug("Using thumbnail image as Version media")
            if thumbnail_path:
                self.parent.shotgun.upload(
                        entity_type="Version",
                        entity_id=item.properties["sg_version_data"]["id"],
                        path=thumbnail_path,
                        field_name="sg_uploaded_movie"
                    )
            else:
                self.logger.debug("Converting file to LMV to extract thumbnails")
                output_directory, thumbnail_path = self._get_thumbnail_from_lmv(item)
                if thumbnail_path:
                    self.parent.shotgun.upload(
                        entity_type="Version",
                        entity_id=item.properties["sg_version_data"]["id"],
                        path=thumbnail_path,
                        field_name="sg_uploaded_movie"
                    )
                    self.parent.shotgun.upload_thumbnail(
                        entity_type="Version",
                        entity_id=item.properties["sg_version_data"]["id"],
                        path=thumbnail_path
                    )
                self.logger.debug("Deleting temporary folder")
                shutil.rmtree(output_directory)

    def _translate_file_to_lmv(self, item):
        """
        Translate the current Alias file as an LMV package in order to upload it to Shotgun as a 3D Version

        :param item: Item to process
        :returns:
            - The path to the LMV zip file
            - The path to the LMV thumbnail
            - The path to the temporary folder where the LMV files have been processed
        """

        framework_lmv = self.load_framework("tk-framework-lmv_v0.1.x")
        translator = framework_lmv.import_module("translator")

        # translate the file to lmv
        lmv_translator = translator.LMVTranslator(item.properties.path)
        self.logger.info("Converting file to LMV")
        lmv_translator.translate()

        # package it up
        self.logger.info("Packaging LMV files")
        package_path, thumbnail_path = lmv_translator.package(
            svf_file_name=str(item.properties["sg_version_data"]["id"]),
            thumbnail_path=item.get_thumbnail_as_path()
        )

        if not thumbnail_path and item.type_spec == "file.vred":
            thumbnail_path = os.path.join(
                self.disk_location,
                "icons",
                "no_preview_vred.png"
            )

        return package_path, thumbnail_path, lmv_translator.output_directory

    def _get_thumbnail_from_lmv(self, item):
        """
        Extract the thumbnail from the source file, using the LMV conversion

        :param item: Item to process
        :returns:
            - The path to the temporary folder where the LMV files have been processed
            - The path to the LMV thumbnail
        """

        framework_lmv = self.load_framework("tk-framework-lmv_v0.1.x")
        self.logger.info("___debug_Dev___ {}".format(framework_lmv))
        translator = framework_lmv.import_module("translator")

        # translate the file to lmv
        lmv_translator = translator.LMVTranslator(item.properties.path)
        self.logger.info("Converting file to LMV")
        lmv_translator.translate()

        self.logger.info("Extracting thumbnails from LMV")
        thumbnail_path = lmv_translator.extract_thumbnail()
        if not thumbnail_path:
            if item.type_spec == "file.vred":
                self.logger.warning("Couldn't retrieve thumbnail data from LMV. Version will use a default image.")
                thumbnail_path = os.path.join(
                    self.disk_location,
                    "icons",
                    "no_preview_vred.png"
                )
            else:
                self.logger.warning("Couldn't retrieve thumbnail data from LMV. Version won't have any associated media")

        return lmv_translator.output_directory, thumbnail_path
