"""
A collection of functions related to Open edX Integration with L&D

"""
import sys
from datetime import datetime, timedelta
import json
import re

import requests
import adal


# pylint: disable=line-too-long
# pylint: disable=W0703

class EdxIntegration(object):
    """
    **Use cases**

    Get the data from OpenEdx and post the data to L&D in MSI(Managed Service Identity)
    enabled Linux environment.

        1) GET secrets from Azure key vault
        2) GET data from Edx
        3) Mapping the data
        4) POST the data to L&D

    """

    def __init__(self, logger=None):

        # get reference to the user-specified python logger that has already been initialized
        self.logger = logger

    def log(self, message, message_type="info"):

        """
        Log a message

        :param message: the message to log
        :param message_type: the type of log message (info, warning, error or debug).
                             If a message is not info or warning, it falls back to debug

        """

        if self.logger:
            if message_type == "info":
                self.logger.info(message)

            elif message_type == "warning":
                self.logger.warning(message)
            elif message_type == "error":
                self.logger.error(message)
            else:
                self.logger.debug(message)

    def get_access_token(self):

        """

        Get OAuth2 access token for REST API call using azure MSI extension

        """

        # the following variables remain same for any MSI enabled Linux environment
        # MSI runs on localhost:50342, port number of url should not be changed
        resource = 'https://vault.azure.net'
        url = 'http://localhost:50342/oauth2/token'
        data = dict(resource=resource)
        headers = dict(MetaData='true')

        response = requests.post(url, data=data, headers=headers, timeout=2)

        if not response.ok:
            raise RuntimeError(response.content)

        else:
            self.log("Got OAuth2 access token using MSI")

        return response.json()['access_token']

    def get_access_token_ld(
            self,
            ldauthorityhosturl,
            ldtenant,
            ldresource,
            ldclientid,
            ldclientsecret
    ):

        """
        Get OAuth2 access token for REST API call for L&D services

        :param ldtenant: tenant id of the AAD application
        :param ldresource: L&D resource url
        :param ldclientid: client id of the AAD application
        :param ldclientsecret: client secret provided by L&D
        :return: access token

        """
        authority_url = "{0}/{1}".format(ldauthorityhosturl, ldtenant)
        context = adal.AuthenticationContext(
            authority_url, validate_authority=ldtenant != 'adfs',
            api_version=None)

        token = context.acquire_token_with_client_credentials(
            ldresource,
            ldclientid,
            ldclientsecret)

        if token['accessToken']:
            self.log("Got Oauth2 access token for L&D REST API")

            return token['accessToken']

        else:
            raise Exception("Un-handled exception occured while accessing the token for L&D")

    def get_key_vault_secret(
            self,
            access_token,
            key_vault_url,
            key_name,
            api_version='2016-10-01'
    ):
        """

        Get value of a key from Azure Key-vault

            1) this function calls a local MSI endpoint to get an access token

            2) MSI uses the locally injected credentials to get an access token from Azure AD

            3) returned access token can be used to authenticate to an Azure service

        :param access_token: access_token obtained from azure AD tenant
        :param keyvault_url: url of the key_vault
        :param key_name: name of the key_vault
        :param api_version: GRAPH api version for the key_vault
        :return: secret value for the provided key

        """

        headers_credentials = {'Authorization': 'Bearer' + ' ' + (access_token)}
        request_url = "{}/secrets/{}?api-version={}".format(key_vault_url, key_name, api_version)
        response = requests.get(request_url, headers=headers_credentials, timeout=2)

        if response.ok:
            self.log("Got the secret key %s from key vault", key_name)

        else:
            self.log("Un-handled exception occurred while accessing %s from key vault", key_name)
            sys.exit(1)

        return response.json()['value']

    def get_api_data(self, request_url, headers):

        """
        Get the data from the provided api url with optional headers using requests python library

        :param request_url: api url to get the data
        :param headers: headers for the api request. defaults to None
        :return: return the api data

        """

        try:
            results = requests.get(request_url, headers=headers, verify=False, timeout=2).json()

            return results

        except Exception as exception:
            self.log(exception, "debug")


    def get_course_catalog_data(self, request_url, headers=None):
        """
        returns data with combined paginated responses for a given api url with optional headers

        :param request_url: api url to get the data
        :param headers: required headers obtained from open edx
        :return: return the results including the paginated data

        """
        self.log("Calling OpenEdx Course Catalog API")

        user_data = self.get_api_data(request_url, headers)
        req_api_data = user_data['results']

        while user_data['pagination']['next']:

            user_data = self.get_api_data(user_data['pagination']['next'], headers)
            req_api_data = req_api_data + user_data['results']

        return req_api_data

    def catalog_data_mapping(self, source_system_id, course_catalog_data):

        """

        mapping the provided EDX data to L&D data format

        :param course_catalog_data: course catalog data obtained from edx
        :param source_system_id: system_id provided by L&D for OXA
        :return: mapped course catalog data to L&D

        """
        self.log("Mapping the course catalog data to L&D format")
        all_course_catalog = []
        ld_catalog = {}

        for each in course_catalog_data:
            ld_catalog["Confidential"] = "false"
            ld_catalog["BIClassification"] = "MBI"
            ld_catalog["BusinessOrg"] = "null"
            ld_catalog["IsPrimary"] = "true"
            ld_catalog["IsShareable"] = "null"
            ld_catalog["CourseType"] = "Build"
            ld_catalog["HideInSearch"] = "hidden"
            ld_catalog["HideInRoadMap"] = "null"
            ld_catalog["ParentSourceSystemId"] = "0"
            ld_catalog["Deleted"] = "false"
            ld_catalog["SourceSystemid"] = source_system_id
            # ld_catalog["Language"] = "en-us"
            ld_catalog["Version"] = "1"
            ld_catalog["Brand"] = "Infopedia"
            ld_catalog["Modality"] = "OLT"
            ld_catalog["MediaType"] = "Course"
            ld_catalog["Status"] = "Active"
            ld_catalog["DescriptionLong"] = "null"
            if each['end']:
                ld_catalog["SunsetDate"] = each['end'].split('T')[0]
            ld_catalog["Keywords"] = each['name']
            ld_catalog["ThumbnailLargeUri"] = each['media']['image']['large']
            if each['enrollment_start']:
                ld_catalog["AvailabilityDate"] = each['enrollment_start'].split('T')[0]
            #ld_catalog["CreatedDateAtSource"] = datetime.now().replace(microsecond=0).isoformat()
            ld_catalog["Name"] = each['name']
            ld_catalog["Url"] = each['blocks_url'].split('/')[0] + '//' + each['blocks_url'].split('/')[2] + "/courses/" + each['course_id'] + "/about"
            ld_catalog["DescriptionShort"] = "null"
            ld_catalog["ThumbnailShort"] = each['media']['image']['small']
            ld_catalog["TrainingOrgs"] = each['org']
            ld_catalog["ExternalId"] = each['course_id'].split(':')[1]
            all_course_catalog.append(ld_catalog)
            ld_catalog = {}
        return json.dumps(all_course_catalog)

    def post_data_ld(self, url, ld_headers, data):
        """

        POST data to L&D services
        :param url: API Endpoint to post the data
        :param headers: required L&D headers
        :param data: data that needs to be posted on L&D

        :return: API json response

        """
        self.log("Preparing to post the data to L&D Course catalog API")
        response = requests.post(url, data=data, headers=ld_headers)
        if response.ok:
            message = "Data posted successfully with %s" % response
            self.log(message, "info")

        else:
            self.log("Un-handled exception occurred while posting the data")
            sys.exit(1)

        return response.json()



    def mapping_consumption_data(self, data, source_system_id, submitted_by):
        """

        Map edX course consumption data to L&D data
        :param data: source raw data
        :param source_system_id: source system ID for OXA in L&D environment
        :return: Data after Mapping

        """
        all_user_grades = []
        ld_user = {}

        for user in data:
            # check if user email contains '@microsoft.com'
            if not bool(re.search('(?i)^(?:(?!(@microsoft.com)).)+$', user['username'])):
                ld_user["UserAlias"] = user['email']
                ld_user["ExternalId"] = user['course_key']
                # ld_user["ConsumptionStatus"] = user['letter_grade']
                # ld_user["grade"] = user[3]
                ld_user["SourceSystemId"] = source_system_id
                ld_user["PersonnelNumber"] = 0
                ld_user["SFSync"] = 0
                ld_user["UUID"] = "null"
                ld_user["ActionVerb"] = "null"
                ld_user["ActionValue"] = 0
                # ld_user["CreatedDate"]
                ld_user["CreatedDate"] = datetime.now().replace(microsecond=0).isoformat()
                ld_user["SubmittedBy"] = submitted_by
                ld_user["ActionFlag"] = "null"
                if ld_user['letter_grade'] == 'Pass':
                    ld_user["ConsumptionStatus"] = 'Passed'
                elif ld_user['letter_grade'] == 'Fail':
                    ld_user["ConsumptionStatus"] = "Failed"
                else:
                    ld_user["ConsumptionStatus"] = "InProgress"

            all_user_grades.append(ld_user)
            ld_user = {}

        return json.dumps(all_user_grades)

    def get_and_post_consumption_data(
            self,
            request_edx_url,
            edx_headers,
            ld_headers,
            consumption_url_ld,
            source_system_id,
            submitted_by,
            api_time_log_file,
            time_delta_retention
    ):

        """

        1. Get consumption data from edX
        2. Map the data
        3. POST the data to L&D

        :param request_edx_url: OpenEdx Bulk grades api URL
        :param edx_headers: OpenEdx Headers
        :param ld_headers: L&D Authorization headers
        :param consumption_url_ld: L&D consumption API Endpoint
        :param source_system_id: L&D source system id for OXA

        """

        try:
            start_date = open(api_time_log_file, 'r')
            start_time = start_date.read()
        except FileNotFoundError:
            start_date = open(api_time_log_file, 'w')
            start_time = ''

        start_date.close()
        end_date = (datetime.now()-timedelta(minutes=time_delta_retention)).replace(microsecond=0).isoformat()
        request_edx_url = request_edx_url + '&start_date=' + start_time + '&end_date=' + end_date

        user_consumption_data = self.get_api_data(request_edx_url, edx_headers)
        self.post_data_ld(consumption_url_ld, ld_headers, self.mapping_consumption_data(user_consumption_data['results'], source_system_id, submitted_by))

        while user_consumption_data['pagination']['next']:
            user_consumption_data = self.get_api_data(user_consumption_data['pagination']['next'], edx_headers)
            self.post_data_ld(consumption_url_ld, ld_headers, self.mapping_consumption_data(user_consumption_data['results'], source_system_id, submitted_by))
        write_time = open(api_time_log_file, 'w')
        write_time.write(end_date)
        write_time.close()
