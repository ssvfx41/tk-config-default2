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

        ## DEBUG
        # import sys
        # sys.path.append("/Users/oues/python_libs")
        # import ptvsd
        # ptvsd.enable_attach(redirect_output=True)
        # ptvsd.wait_for_attach()
        # ## END DEBUG

        # create the Version in Shotgun
        super(UploadVersionPlugin, self).publish(settings, item)

        # generate the Version content: LMV file or simple 2D thumbnail
        if settings.get("3D Version").value is True:
            self.logger.debug("Creating LMV files from source file")

            # translate the file to lmv and upload the corresponding package to the Version
            package_path, thumbnail_path, output_directory = self._translate_file_to_lmv(
                item, settings.get("Translation Worker").value
            )

            self.logger.debug("Translation package path {}".format(package_path))
            self.logger.debug("Translation thumbnail path {}".format(thumbnail_path))
            self.logger.debug("Uploading LMV file to Shotgun")
            self.logger.debug("parent {}, shotgun {}".format(self.parent, self.parent.shotgun))

            self.parent.shotgun.update(
                entity_type="Version",
                entity_id=item.properties["sg_version_data"]["id"],
                data={
                    "sg_translation_type": "LMV"
                }
            )
            self.parent.shotgun.upload(
                entity_type="Version",
                entity_id=item.properties["sg_version_data"]["id"],
                path=package_path,
                field_name="sg_uploaded_movie"
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

    def _translate_file_to_lmv(self, item, translation_worker="local"):
        """
        Translate the current Alias file as an LMV package in order to upload it to Shotgun as a 3D Version

        :param item: Item to process
        :returns:
            - The path to the LMV zip file
            - The path to the LMV thumbnail
            - The path to the temporary folder where the LMV files have been processed
        """

        package_path = None
        thumbnail_path = None
        output_directory = None

        if translation_worker == "local":
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

            # return package_path, thumbnail_path, lmv_translator.output_directory
            output_directory = lmv_translator.output_directory
        
        elif translation_worker == "forge":
            framework_forge = self.load_framework("tk-framework-forge_v0.1.x")            
            forge_api = framework_forge.import_module("forge_api")
            
            forge_client = forge_api.ForgeClient()

            # Authenticate with forge
            forge_client._authenticate()

            # Create the S3 bucket if not already created, to upload our files to
            forge_client._create_bucket()

            # Upload file pointed to at the item properties path, to forge
            upload_data = forge_client.upload_file(item.properties.path, item.name)

            # Get the object id from the payload returned from forge and base64 safe url encode it, to
            # pass to post translation job (as URN)
            # 
            # NOTE: Should we use tank_endor representer.py instead?
            urn = base64.urlsafe_b64encode(bytes(upload_data["objectId"].rstrip('=')))
            result = forge_client.post_job(urn, upload_data["objectKey"])

            # Poll the manifest for the job we kicked off to know when our job has completed
            # 
            # TODO: make this op async, or return right away since we don't really need to wait for the job complete,
            # we already have the urn, but we would need to update the status once complete
            job_finished = False
            manifest = None
            while not job_finished:
                manifest = forge_client.get_manifest(result["urn"])
                job_finished = manifest["status"] != "pending" and manifest["status"] != "inprogress"
            
            if manifest and manifest["status"] == "success":
                # Forge Option #1:
                # Set custom field on Version for "URN" value for SG to load in Forge Viewer
                # Pro: fast operation to translate -- job is sent to Forge and we're free to go on
                # Con: requires SG code change to load using URN, in addition to local URL. As well,
                # a Forge App/credentials needs to be shared between Toolkit and SG
                self.parent.shotgun.update(
                    entity_type="Version",
                    entity_id=item.properties["sg_version_data"]["id"],
                    data={
                        "sg_urn": manifest["urn"]
                    }
                )

                # Forge Option #2:
                # More of a proof of concept, but we can download the translation files from
                # Forge, and then pass to SG API to upload to S3 for 3D Viewer to access in SG
                # Pro: No code changes to SG, only toolkit
                # Con: Redundancy in uploading to Forge, which uploads to S3 -- then we download the
                # translation files to upload again to SG this time, which also stores it on S3
                # NOTE: could we modify SG to point to Forge S3 location? Then we can get the best
                # of #1 and #2, but uploading to Forge and minimal code change to SG to get S3 files

                # Parse the manifest to extract the derviatives to download
                (derivatives, thumbnails) = forge_client.parse_manifest(manifest['derivatives'])

                # Set up directories to download derivatives and zip them up
                # TODO: use temp dir and then remove it
                version_id = str(item.properties["sg_version_data"]["id"])
                zip_directory = "/opt/shotgun/forge-test/"

                # The root directory to where derivatives will be downloaded to.
                root_directory = "/opt/shotgun/forge-test/{}/".format(version_id)
                if not os.path.isdir(root_directory):
                    os.mkdir(root_directory) 

                # Directory that derivatives will be downloaded to.
                output_directory = os.path.join(root_directory, "1")
                if not os.path.isdir(output_directory):
                    os.mkdir(output_directory)

                # Download all derivates from Forge, including any file dependencies
                for derivative in derivatives:
                    # Remember the SVF file name so that we can rename it later
                    if forge_client.is_svf(derivative):
                        derivative["root_filename"] = "{}.svf".format(version_id)
            
                    path = os.path.join(output_directory, derivative["root_filename"])
                    forge_client.download_derivative(manifest["urn"], derivative["urn"], path)
                    
                    # Download any dependencies for the derivative
                    for filename in derivative["files"]:
                        derivative_urn = os.path.join(derivative["base_path"], filename)
                        path = os.path.join(output_directory, filename)
                        forge_client.download_derivative(manifest["urn"], derivative_urn, path)

                # get the thumbnail data
                thumbnail_data = None
                thumbnail_source_path = item.get_thumbnail_as_path()
                if thumbnail_source_path:
                    with open(thumbnail_source_path, "rb") as fp:
                        thumbnail_data = fp.read()
                elif thumbnails:
                    # Just take the first thumbnail for now.
                    thumbnail_path = os.path.join(output_directory, thumbnails[-1]["root_filename"])
                    with open(thumbnail_path, "rb") as fp:
                        thumbnail_data = fp.read()

                # write the thumbnails on disk
                if thumbnail_data:
                    images_dir_path = os.path.join(root_directory, "images")
                    if not os.path.exists(images_dir_path):
                        os.makedirs(images_dir_path)

                    thumbnail_path = os.path.join(
                        images_dir_path, "{}.jpg".format(version_id)
                    )
                    with open(thumbnail_path, "wb") as fp:
                        fp.write(thumbnail_data)

                if not thumbnail_path and item.type_spec == "file.vred":
                    thumbnail_path = os.path.join(
                        self.disk_location,
                        "icons",
                        "no_preview_vred.png"
                    )
                
                # Zip the package
                zip_path = shutil.make_archive(
                    base_name=os.path.join(zip_directory, version_id),
                    format="zip",
                    root_dir=root_directory,
                )

                # Update the translation type to LMV and upload the zip folder, as we do for local translations.
                self.parent.shotgun.update(
                    entity_type="Version",
                    entity_id=item.properties["sg_version_data"]["id"],
                    data={
                        "sg_translation_type": "LMV"
                    }
                )
                self.parent.shotgun.upload(
                    entity_type="Version",
                    entity_id=item.properties["sg_version_data"]["id"],
                    path=zip_path,
                    field_name="sg_uploaded_movie"
                )

                # FIXME thumbnails only worked a few times? now they do not...
                # if the Version thumbnail is empty, update it with the newly created thumbnail
                if not item.get_thumbnail_as_path() and thumbnail_path:
                    self.parent.shotgun.upload_thumbnail(
                        entity_type="Version",
                        entity_id=item.properties["sg_version_data"]["id"],
                        path=thumbnail_path
                    )

            else:
                self.logger.error("Forge Cloud Translation -- manifest failed")
            
            # Done. Close the forge connection.
            forge_client._close_connection()
    
        else:
            self.logger.error("Unknown Translation Worker Type")
        
        return package_path, thumbnail_path, output_directory


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
