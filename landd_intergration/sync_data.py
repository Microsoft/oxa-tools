"""

Course consumption syncronization between OXA and  L&D

"""
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
import configparser
import landd_integration



CONFIG = configparser.ConfigParser()
CONFIG.read('oxa_landd_config.cfg')

#pylint: disable=line-too-long
logging.basicConfig(filename='course_consumption.log', format='%(asctime)s' '%(message)s', level=logging.DEBUG)
LOG = logging.getLogger(__name__)
HANDLER = logging.handlers.TimedRotatingFileHandler('course_consumption.log', when="d", interval=1, backupCount=10)
LOG.addHandler(HANDLER)


def sync_course_consumption():
    """
    1) GET access token from Azure tenant using MSI
    2) GET secrets from Azure keyvault using the access token
    3) GET the Course catalog data from OpenEdx using the secrets obtined from Azure key vault
    4) Map and process the OpenEdx course catalog data with L&D Catalog Consumption API request body
    5) POST the mapped data to L&D Catalog Consumption API

    """
    LOG.debug("Starting the Course consumption Interation process")

    # initialize the key variables
    catalog_service = landd_integration.EdxIntegration(logger=LOG)

    secret_keys_dict = {}
    attempts = 0

    while attempts < int(CONFIG.get('general', 'number_of_retry_attempts')):
        try:

            for azure_key_vault_key, api_key in zip(CONFIG.get('azure_key_vault', 'azure_key_vault_keys').split('\n'), CONFIG.get('api_secret_keys', 'api_keys').split('\n')):
                # get secrets from Azure Key Vault
                secret_keys_dict[api_key] = catalog_service.get_key_vault_secret(catalog_service.get_access_token(), CONFIG.get('azure_key_vault', 'key_vault_url'), azure_key_vault_key)


            # construct headers using key vault secrets
            authorization = '{0} {1}'.format('Bearer', secret_keys_dict['edx_access_token'])
            edx_headers = dict(Authorization=authorization, X_API_KEY=secret_keys_dict['edx_api_key'])


            headers = {
                'Content-Type': 'application/json',
                'Ocp-Apim-Subscription-Key': secret_keys_dict['landd_subscription_key'],
                'Authorization': catalog_service.get_access_token_ld(
                    CONFIG.get('landd', 'landd_authorityhosturl'),
                    CONFIG.get('landd', 'landd_tenant'),
                    CONFIG.get('landd', 'landd_resource'),
                    secret_keys_dict['landd_clientid'],
                    secret_keys_dict['landd_clientsecret']
                    )
                }
            if sys.argv[1] == "course_consumption":
                catalog_service.get_and_post_consumption_data(CONFIG.get('edx', 'edx_course_consumption_url'), edx_headers, headers, CONFIG.get('landd', 'landd_consumption_url'), CONFIG.get('landd', 'source_system_id'))
                LOG.debug("End of the Catalog Integration process")
            elif sys.argv[1] == "course_catalog":
                catalog_data = catalog_service.get_course_catalog_data(CONFIG.get('edx', 'edx_course_catalog_url'), edx_headers)
                catalog_service.post_data_ld(CONFIG.get('landd', 'landd_catalog_url'), headers, catalog_service.catalog_data_mapping(CONFIG.get('landd', 'source_system_id'), catalog_data))
                LOG.debug("End of the Course Catalog Integration process")
            break

        except Exception: # pylint: disable=W0703

            attempts += 1
            LOG.error("Exception occured while running the script", exc_info=True)

if __name__ == "__main__":
    sync_course_consumption()  # pylint: disable=no-value-for-parameter
