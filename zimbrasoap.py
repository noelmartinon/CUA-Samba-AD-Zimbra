###############################################################################
# ZimbraSoap - Python Zimbra Soap class                                       #
#                                                                             #
# Copyright (C) 2024  Noël MARTINON - noel.martinon@gmail.com                 #
#                                                                             #
# This program is free software: you can redistribute it and/or modify        #
# it under the terms of the GNU General Public License as published by        #
# the Free Software Foundation, either version 3 of the License, or           #
# (at your option) any later version.                                         #
#                                                                             #
# This program is distributed in the hope that it will be useful,             #
# but WITHOUT ANY WARRANTY; without even the implied warranty of              #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the               #
# GNU General Public License for more details.                                #
#                                                                             #
# You should have received a copy of the GNU General Public License           #
# along with this program.  If not, see <http://www.gnu.org/licenses/>.       #
###############################################################################

from lxml import etree
import requests
import html
import xmltodict
import inspect


class ZimbraSoap(object):
    __message = ''
    __xml_response = ''
    __last_xml_func_called_successfully = ''
    __url_api = ''
    __admin_username = ''
    __admin_token = ''
    __delegated_token = ''
    __account = ''

    def __init__(self, url_api, admin_username, admin_password):
        self.__url_api = url_api
        self.__admin_username = admin_username

        try:
            self.__admin_token = self.get_admin_token(admin_username, admin_password)
        except:
            raise Exception('Error getting tokens, check the credentials.')

    def get_xml_response(self):
        return self.__xml_response

    def get_message(self):
        return self.__message

    def xml_attrib_to_dict(self, xml_string, urn, xpath):
        '''
        urn is zimbraAdmin, zimbraAccount, zimbraMail, zimbraRepl,
            zimbraSync, zimbraVoice or zimbraAdminExt
        '''
        xmldict = {}
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
            '': 'urn:%s' % (urn),
        }
        xml_element = etree.fromstring(xml_string).find(xpath, namespaces)
        for key, value in xml_element.attrib.items():
            xmldict[key] = value
        return xmldict

    def xml_text_to_dict(self, xml_string, urn, xpath, attrib_key):
        '''
        urn is zimbraAdmin, zimbraAccount, zimbraMail, zimbraRepl,
            zimbraSync, zimbraVoice or zimbraAdminExt
        '''
        xmldict = {}
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
            '': 'urn:%s' % (urn),
        }
        xml_element = etree.fromstring(xml_string).findall(xpath, namespaces)
        for xmldict_el in xml_element:
            xmldict_name = xmldict_el.attrib[attrib_key]
            xmldict[xmldict_name] = xmldict_el.text
        return xmldict

    def get_admin_token(self, admin_username, admin_password):
        '''
        Get admin token
        '''
        # Set XML Request
        admin_token_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <format type="xml"/>
            </context>
        </soap:Header>
        <soap:Body>
            <AuthRequest xmlns="urn:zimbraAdmin">
                <name>%s</name>
                <password>%s</password>
            </AuthRequest>
        </soap:Body>
        </soap:Envelope>''' % (admin_username, admin_password)

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=admin_token_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Body/soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return None

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        # Get the token
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
            '': 'urn:zimbraAdmin',  # avoid specifying it in xpath,
                                    # for example './/{urn:zimbraAdmin}authToken'
        }
        admin_token = etree.fromstring(r.content).find('.//authToken', namespaces)
        return admin_token.text

    def get_delegated_token(self, account):
        '''
        Get delegated user token
        '''
        # Do not get token if always done for current account
        if self.__account == account and len(self.__delegated_token) > 0:
            return self.__delegated_token

        # Set XML Request
        delegated_token_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
            </context>
        </soap:Header>
        <soap:Body>
            <DelegateAuthRequest duration="86400" xmlns="urn:zimbraAdmin">
                <account by="name">%s</account>
            </DelegateAuthRequest>
        </soap:Body>
        </soap:Envelope>''' % (self.__admin_token, account)

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=delegated_token_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Body/soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            self.__delegated_token = ''
            return ''

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        # Get the token
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
            '': 'urn:zimbraAdmin'
        }
        delegated_token = etree.fromstring(r.content).find('.//authToken', namespaces)
        self.__delegated_token = delegated_token.text
        self.__account = account
        return delegated_token.text

    def get_info(self, account, sections=''):
        '''
        Get user account informations
        sections: all or part of 'mbox,prefs,attrs,zimlets,props,idents,sigs,dsrcs,children'
        '''
        # Clear the ZimbraSoap instance variables
        self.__message = ''
        self.__xml_response = ''

        # Get delegated token
        if not self.get_delegated_token(account):
            return None

        # Set XML Request
        info_request_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
                <session/>
                <account by="name">%s</account>
                <userAgent name="zclient" version="10.0.0_GA_4518"/>
            </context>
        </soap:Header>
        <soap:Body>
            <GetInfoRequest sections="%s" rights="" xmlns="urn:zimbraAccount"/>
        </soap:Body>
        </soap:Envelope>''' % (self.__delegated_token, account, sections)

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=info_request_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Body/soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return None

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        return r.content

    def get_info_value(self, account, value, xml_string=''):
        '''
        Get a user account value from its account informations
        Returns the value from xml response
        '''
        if self.__last_xml_func_called_successfully != 'get_info':
            self.get_info(account)

        if not xml_string:
            if self.__xml_response:
                xml_string = self.__xml_response
            else:
                self.__message = 'Error account ID not found.'
                return None

        # Proceed XML
        xmldict = xmltodict.parse(xml_string)
        value = xmldict['soap:Envelope']['soap:Body']["GetInfoResponse"][value]

        return value

    def get_prefs(self, account, prefs_list=[]):
        '''
        Get user account preferences
        Returns a dictionary containing the account preferences
        '''
        # Clear the ZimbraSoap instance variables
        self.__message = ''
        self.__xml_response = ''

        # Get delegated token
        if not self.get_delegated_token(account):
            return None

        # Set preferences request
        prefs_xml = ''
        if len(prefs_list):
            for pref in prefs_list:
               prefs_xml = '%s<pref name="%s"/>' %(prefs_xml, pref)

        # Set XML Request
        get_prefs_request_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
                <session/>
                <account by="name">%s</account>
                <userAgent name="zclient" version="10.0.0_GA_4518"/>
            </context>
        </soap:Header>
        <soap:Body>
            <GetPrefsRequest xmlns="urn:zimbraAccount">%s</GetPrefsRequest>
        </soap:Body>
        </soap:Envelope>''' % (self.__delegated_token, account, prefs_xml)

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=get_prefs_request_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Body/soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return None

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        # Proceed XML
        prefs = {}
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
            '': 'urn:zimbraAccount',
        }
        xml_element = etree.fromstring(self.__xml_response).findall('.//soap:Body/*/pref[@name]', namespaces)
        for pref_el in xml_element:
            pref_name = pref_el.attrib['name']
            prefs[pref_name] = pref_el.text

        return prefs

    def modify_prefs(self, account, prefs_list):
        '''
        Set user account preferences
        Returns a boolean according to success or not of the creation
        '''
        # Clear the ZimbraSoap instance variables
        self.__message = ''
        self.__xml_response = ''

        # Get delegated token
        if not self.get_delegated_token(account):
            return False

        # Set preferences request
        prefs_xml = ''
        if len(prefs_list):
            for pref in prefs_list:
                prefs_xml = '%s<pref name="%s">%s</pref>' %(prefs_xml, pref, prefs_list[pref])

        # Set XML Request
        modify_prefs_request_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
                <session/>
                <account by="name">%s</account>
                <userAgent name="zclient" version="10.0.0_GA_4518"/>
            </context>
        </soap:Header>
        <soap:Body>
            <ModifyPrefsRequest xmlns="urn:zimbraAccount">%s
            </ModifyPrefsRequest>
        </soap:Body>
        </soap:Envelope>''' % (self.__delegated_token, account, prefs_xml)

        # Reencode to be able to use accents
        modify_prefs_request_xml = modify_prefs_request_xml.encode("utf-8").decode("latin-1")

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=modify_prefs_request_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Body/soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return False

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        return True

    def get_identities(self, account):
        '''
        Get user account identities
        Returns an xml string containing all the identities
        '''
        # Clear the ZimbraSoap instance variables
        self.__message = ''
        self.__xml_response = ''

        # Get delegated token
        if not self.get_delegated_token(account):
            return None

        # Set XML Request
        get_identities_request_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
                <session/>
                <account by="name">%s</account>
                <userAgent name="zclient" version="10.0.0_GA_4518"/>
            </context>
        </soap:Header>
        <soap:Body>
            <GetIdentitiesRequest xmlns="urn:zimbraAccount"/>
        </soap:Body>
        </soap:Envelope>''' % (self.__delegated_token, account)

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=get_identities_request_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Body/soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return None

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        return r.content

    def get_identity(self, account, name):
        '''
        Get user account identity
        Returns a dictionary containing the identity id and the attibutes
        Example usage of returned value, get the attribut 'zimbraPrefForwardReplyFormat':
            identity = zs.get_identity(email, 'DEFAULT')
            value = next(item for item in identity['a'] if item["@name"] == 'zimbraPrefForwardReplyFormat')['#text']
        '''
        # Get all user identities
        if self.__last_xml_func_called_successfully != 'get_identities':
            self.get_identities(account)

        # Proceed XML
        xmldict = xmltodict.parse(self.__xml_response)
        identities = xmldict['soap:Envelope']['soap:Body']["GetIdentitiesResponse"]['identity']
        if isinstance(identities, list):
            identity = next(item for item in identities if item["@name"] == name)
        elif identities["@name"] == name:
            identity = identities
        else:
            return None

        return identity

    def modify_identity(self, account, name, attrs_name_list):
        '''
        Modify user account identity
        Returns a boolean according to success or not of the implementation
        '''
        # Clear the ZimbraSoap instance variables
        self.__message = ''
        self.__xml_response = ''

        # Get delegated token
        if not self.get_delegated_token(account):
            return False

        # Set preferences request
        attrs_xml = ''
        if len(attrs_name_list):
            for attr in attrs_name_list:
                attrs_xml = '%s<a name="%s">%s</a>' %(attrs_xml, attr, attrs_name_list[attr])

        # Set XML Request
        modify_identities_request_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
                <session/>
                <account by="name">%s</account>
                <userAgent name="zclient" version="10.0.0_GA_4518"/>
            </context>
        </soap:Header>
        <soap:Body>
            <ModifyIdentityRequest xmlns="urn:zimbraAccount">
                <identity name="%s">%s</identity>
            </ModifyIdentityRequest>
        </soap:Body>
        </soap:Envelope>''' % (self.__delegated_token, account, name, attrs_xml)

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=modify_identities_request_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Body/soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return False

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        return True

    def subscribe_distributionlist(self, account, name):
        '''
        Adding user to a distribution list
        Returns a boolean according to success or not of the implementation
        '''
        # Clear the ZimbraSoap instance variables
        self.__message = ''
        self.__xml_response = ''

        # Get delegated token
        if not self.get_delegated_token(account):
            return False

        # Set XML Request
        modify_identities_request_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
                <session/>
                <account by="name">%s</account>
                <userAgent name="zclient" version="10.0.0_GA_4518"/>
            </context>
        </soap:Header>
        <soap:Body>
            <SubscribeDistributionListRequest op="subscribe" xmlns="urn:zimbraAccount">
                <dl by="name">%s</dl>
            </SubscribeDistributionListRequest>
        </soap:Body>
        </soap:Envelope>''' % (self.__delegated_token, account, name)

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=modify_identities_request_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Body/soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return False

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        return True

    def add_distribution_listmember(self, name, account):
        '''
        Adding members to a distribution list
        Returns a boolean according to success or not of the implementation
        '''
        # Clear the ZimbraSoap instance variables
        last_xml_message = self.__xml_response
        self.__message = ''
        self.__xml_response = ''

        # Get distribution list id
        if self.__last_xml_func_called_successfully != 'get_distribution_lists':
            domain = name.split('@')[1]
            self.get_distribution_lists(domain)
            last_xml_message = self.__xml_response
        dls_xml = xmltodict.parse(last_xml_message)
        dls = dls_xml['soap:Envelope']['soap:Body']["GetAllDistributionListsResponse"]['dl']
        dl = next(item for item in dls if item["@name"] == name)
        dl_id = dl['@id']

        # Set XML Request
        modify_identities_request_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
            </context>
        </soap:Header>
        <soap:Body>
            <AddDistributionListMemberRequest id="%s" xmlns="urn:zimbraAdmin">
                <dlm>%s</dlm>
            </AddDistributionListMemberRequest>
        </soap:Body>
        </soap:Envelope>''' % (self.__admin_token, dl_id, account)

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=modify_identities_request_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Body/soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return False

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        return True

    def get_signatures(self, account):
        '''
        Get all user account signatures
        Returns an xml string containing all the signatures
        '''
        # Clear the ZimbraSoap instance variables
        self.__message = ''
        self.__xml_response = ''

        # Get delegated token
        if not self.get_delegated_token(account):
            return None

        # Set XML Request
        get_identities_request_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
                <session/>
                <account by="name">%s</account>
                <userAgent name="zclient" version="10.0.0_GA_4518"/>
            </context>
        </soap:Header>
        <soap:Body>
            <GetSignaturesRequest xmlns="urn:zimbraAccount"/>
        </soap:Body>
        </soap:Envelope>''' % (self.__delegated_token, account)

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=get_identities_request_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Body/soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return None

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        return r.content

    def get_signature(self, account, name):
        '''
        Get user account signature
        Returns a dictionary containing the signature id and the content
        Example usage: content = get_signature(email,'Signature #1')['content']['#text']
        '''
        # Get all user signatures
        if self.__last_xml_func_called_successfully != 'get_signatures':
            if not self.get_signatures(account):
                return None

        # Proceed XML
        xmldict = xmltodict.parse(self.__xml_response)
        signatures = xmldict['soap:Envelope']['soap:Body']["GetSignaturesResponse"]['signature']
        if isinstance(signatures, list):
            signature = next(item for item in signatures if item["@name"] == name)
        elif signatures["@name"] == name:
            signature = signatures
        else:
            return None

        return signature

    def create_signature(self, account, signature):
        '''
        Create user account signature
        The variable 'signature' is a list:
          name: Name of the signature
          type: Content type 'text/plain' or 'text/html'
          content: Text of the signature
        Returns a boolean according to success or not of the implementation
        '''
        # Clear the ZimbraSoap instance variables
        self.__message = ''
        self.__xml_response = ''

        # Set account variables
        try:
            name = signature['name']
            stype = signature['type']
            content = html.escape(signature['content'])
        except:
            self.__message = 'missing attributes'
            return False

        # Get delegated token
        if not self.get_delegated_token(account):
            return False

        # Set XML Request
        create_identities_request_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
                <session/>
                <account by="name">%s</account>
                <userAgent name="zclient" version="10.0.0_GA_4518"/>
            </context>
        </soap:Header>
        <soap:Body>
            <CreateSignatureRequest xmlns="urn:zimbraAccount">
                <signature name ="%s">
                    <content type="%s">%s</content>
                </signature>
            </CreateSignatureRequest>
        </soap:Body>
        </soap:Envelope>''' % (self.__delegated_token, account, name,
                              stype, content)

        # Reencode to be able to use accents
        create_identities_request_xml = create_identities_request_xml.encode("utf-8").decode("latin-1")

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=create_identities_request_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Body/soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return False

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        return True

    def modify_signature(self, account, signature, create_missing=False):
        '''
        Modify user account signature
        The variable 'signature' is a list:
          name: Name of the signature
          type: Content type 'text/plain' or 'text/html'
          content: Text of the signature
        Returns a boolean according to success or not of the implementation
        '''
        # Clear the ZimbraSoap instance variables
        self.__message = ''
        self.__xml_response = ''

        # Set account variables
        try:
            name = signature['name']
            stype = signature['type']
            content = html.escape(signature['content'])
        except:
            self.__message = 'missing attributes'
            return False

        # Get delegated token
        if not self.get_delegated_token(account):
            return False

        # Get signature id
        try:
            sid = self.get_signature(account, name)['@id']
        except:
            if create_missing:
                return self.create_signature(account, signature)
            self.__message = 'signature "%s" does not exists' % (name)
            return False

        # Set XML Request
        modify_identities_request_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
                <session/>
                <account by="name">%s</account>
                <userAgent name="zclient" version="10.0.0_GA_4518"/>
            </context>
        </soap:Header>
        <soap:Body>
            <ModifySignatureRequest xmlns="urn:zimbraAccount">
                <signature id="%s">
                    <content type="%s">%s</content>
                </signature>
            </ModifySignatureRequest>
        </soap:Body>
        </soap:Envelope>''' % (self.__delegated_token, account,
                              sid, stype, content)

        # Reencode to be able to use accents
        modify_identities_request_xml = modify_identities_request_xml.encode("utf-8").decode("latin-1")

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=modify_identities_request_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Body/soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return None

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        return True

    def get_distribution_lists(self, domain):
        '''
        Get distribution lists
        Returns a dictionary containing the xml response
        '''
        # Clear the ZimbraSoap instance variables
        self.__message = ''
        self.__xml_response = ''

        # Set XML Request
        request_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
                <session/>
                <account by="name">%s</account>
                <userAgent name="zclient" version="10.0.0_GA_4518"/>
            </context>
        </soap:Header>
        <soap:Body>
            <GetAllDistributionListsRequest xmlns="urn:zimbraAdmin">
                <domain by="name">%s</domain>
            </GetAllDistributionListsRequest>
        </soap:Body>
        </soap:Envelope>''' % (self.__admin_token, self.__admin_username,
                              domain)

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=request_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Body/soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return None

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        return xmltodict.parse(self.__xml_response)

    def get_distribution_lists_export(self, domain, emails_prefix=[], email_forward_tag=''):
        '''
        Get distribution list(s) content to dictionary
        emails_prefix: String or list of emails prefix
        email_forward_tag: String append to list's email when email is redirected to another distribution list name
        Returns a list of dictionary containing the distribution list(s)
        '''
        if self.__last_xml_func_called_successfully != 'get_distribution_lists':
            self.get_distribution_lists(domain)

        if isinstance(emails_prefix, str):
            emails_prefix = [emails_prefix]

        # Proceed XML
        distribution_lists = {}
        dls_xml = xmltodict.parse(self.__xml_response)
        dls = dls_xml['soap:Envelope']['soap:Body']["GetAllDistributionListsResponse"]['dl']
        for dl in dls:
            if len(emails_prefix):
                for prefix in emails_prefix:
                    if isinstance(prefix, dict):
                        key = next(iter(prefix))  # Get 1st key
                        val = prefix[key]
                        email = key + '@' + domain
                        email_out = val + '@' + domain
                        if len(email_forward_tag):
                            email_out += ' ' + email_forward_tag
                    else:
                        email = email_out = prefix + '@' + domain
                    if dl['@name'].split('@')[0] == email.split('@')[0]:
                        if 'dlm' in dl:
                            distribution_lists[email_out] = dl['dlm']
                        else:
                            distribution_lists[email_out] = []
                        break

        return distribution_lists

    def get_share_info(self, account):
        '''
        Get share informations
        '''
        # Clear the ZimbraSoap instance variables
        self.__message = ''
        self.__xml_response = ''

        # Get delegated token
        if not self.get_delegated_token(account):
            return None

        # Set XML Request
        share_info_request_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
                <session/>
                <account by="name">%s</account>
                <userAgent name="zclient" version="10.0.0_GA_4518"/>
            </context>
        </soap:Header>
        <soap:Body>
            <GetShareInfoRequest xmlns="urn:zimbraAccount"/>
        </soap:Body>
        </soap:Envelope>''' % (self.__delegated_token, account)

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=share_info_request_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Body/soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return None

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        # Proceed XML
        xmldict = xmltodict.parse(self.__xml_response)
        shares = xmldict['soap:Envelope']['soap:Body']["GetShareInfoResponse"]["share"]

        return shares

    def get_folder(self, account, path):
        '''
        Get folder informations
        '''
        # Clear the ZimbraSoap instance variables
        self.__message = ''
        self.__xml_response = ''

        # Get delegated token
        if not self.get_delegated_token(account):
            return None

        # Set XML Request
        request_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
                <session/>
                <account by="name">%s</account>
                <userAgent name="zclient" version="10.0.0_GA_4518"/>
            </context>
        </soap:Header>
        <soap:Body>
            <GetFolderRequest xmlns="urn:zimbraMail">
                <folder path="%s"/>
            </GetFolderRequest>
        </soap:Body>
        </soap:Envelope>''' % (self.__delegated_token, account, path)

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=request_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Body/soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return None

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        # ~ self.get_folder_export_new(self.__xml_response, path)
        return self.get_folder_export(self.__xml_response, path)

    def get_folder_export(self, xml_string='', path=''):
        '''
        Export response informations from get_folder
        Returns a dict containing attribs (id,name) and items (a tag)
        '''
        if not xml_string:
            if self.__xml_response:
                xml_string = self.__xml_response
            else:
                self.__message = 'Error folder not found.'
                return None

        # Proceed XML
        xmldict = xmltodict.parse(xml_string)
        export = xmldict['soap:Envelope']['soap:Body']["GetFolderResponse"]['folder']

        return export


    def folder_action_share(self, account, foldername, email, grantee_type='usr', perm='r'):
        '''
        Share a user account informations folder
        foldername: e.g. '/Calendar'
        email: email recipient to share
        grantee_type: 'usr' for email user or 'grp' for distribution list
        perm: (r)ead, (w)rite, (i)nsert, (d)elete, (a)dminister
            [Not supported: workflow action (x), view (p)rivate, view (f)reebusy]
        Returns a boolean
        '''
        # Check the variables
        if not grantee_type in ['usr','grp']:
            self.__message = 'Error in share email type.'
            return None
        if not perm in ['r','w','i','d','a']:
            self.__message = 'Error in share permissions.'
            return None

        # Clear the ZimbraSoap instance variables
        self.__message = ''
        self.__xml_response = ''

        # Get delegated token
        if not self.get_delegated_token(account):
            return None

        # Get folder id
        folder = self.get_folder(account, foldername)
        if not folder:
            return None
        folderid = folder['@id']

        # Check already existing grantee
        try:
            grant = folder['acl']['grant']
            if grant['@perm'] == perm and grant['@gt'] == grantee_type:
                return True
        except:
            pass

        # Set XML Request
        share_info_request_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
                <session/>
                <account by="name">%s</account>
                <userAgent name="zclient" version="10.0.0_GA_4518"/>
            </context>
        </soap:Header>
        <soap:Body>
            <FolderActionRequest xmlns="urn:zimbraMail">
                <action id="%s" op="grant">
                    <grant perm="%s" gt="%s" d="%s"/>
                </action>
            </FolderActionRequest>
        </soap:Body>
        </soap:Envelope>''' % (self.__delegated_token, account, folderid,
                              perm, grantee_type, email)

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=share_info_request_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Body/soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return None

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        return True

    def msg_action_delete_byid(self, account, msgid):
        '''
        Delete messages
        msgid: comma separated list of id
        Returns a boolean
        '''
        # Clear the ZimbraSoap instance variables
        self.__message = ''
        self.__xml_response = ''

        # Get delegated token
        if not self.get_delegated_token(account):
            return None

        # Set XML Request
        share_info_request_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
                <session/>
                <account by="name">%s</account>
                <userAgent name="zclient" version="10.0.0_GA_4518"/>
            </context>
        </soap:Header>
        <soap:Body>
            <MsgActionRequest xmlns="urn:zimbraMail">
                <action id="%s" op="delete">
                </action>
            </MsgActionRequest>
        </soap:Body>
        </soap:Envelope>''' % (self.__delegated_token, account, msgid)

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=share_info_request_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Body/soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return None

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        return True

    def msg_action_delete(self, account, query):
        '''
        Delete messages
        query is a string e.g. 'in:inbox is:unread subject:"The mail subject"'
        Returns numbers of messages deleted
        '''
        # Clear the ZimbraSoap instance variables
        self.__message = ''
        self.__xml_response = ''

        # Get delegated token
        if not self.get_delegated_token(account):
            return None

        # Get messages id
        search_msg = self.search_message(account, query)
        if not 'c' in search_msg['soap:Envelope']['soap:Body']["SearchResponse"]:
            return 0
        msgid = ''
        for conversation in search_msg['soap:Envelope']['soap:Body']["SearchResponse"]['c']:
            messages = conversation['m']
            if isinstance(messages, list):
                for msg in messages:
                    msgid += ',' + msg['@id']
            else:
                msgid += ',' + messages['@id']
        msgcount = msgid.count(',')
        msgid = msgid.split(",", 1)[1]

        # Set XML Request
        share_info_request_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
                <session/>
                <account by="name">%s</account>
                <userAgent name="zclient" version="10.0.0_GA_4518"/>
            </context>
        </soap:Header>
        <soap:Body>
            <MsgActionRequest xmlns="urn:zimbraMail">
                <action id="%s" op="delete">
                </action>
            </MsgActionRequest>
        </soap:Body>
        </soap:Envelope>''' % (self.__delegated_token, account, msgid)

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=share_info_request_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Body/soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return None

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        return msgcount

    def search_message(self, account, query):
        '''
        Get messages
        query is a string e.g. 'in:inbox is:unread subject:"The mail subject"'
        '''
        # Clear the ZimbraSoap instance variables
        self.__message = ''
        self.__xml_response = ''

        # Get delegated token
        if not self.get_delegated_token(account):
            return None

        # Set XML Request
        request_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
                <session/>
                <account by="name">%s</account>
                <userAgent name="zclient" version="10.0.0_GA_4518"/>
            </context>
        </soap:Header>
        <soap:Body>
            <SearchRequest xmlns="urn:zimbraMail">
                <query>%s</query>
            </SearchRequest>
        </soap:Body>
        </soap:Envelope>''' % (self.__delegated_token, account, query)

        # Reencode to be able to use accents
        request_xml = request_xml.encode("utf-8").decode("latin-1")

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=request_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Body/soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return None

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        return xmltodict.parse(self.__xml_response)

    def create_mountpoint(self, account, target, name, owner, path):
        '''
        Create mountpoint target to an owner path
        Return True if succeeded
        '''
        # Clear the ZimbraSoap instance variables
        self.__message = ''
        self.__xml_response = ''

        # Get delegated token
        if not self.get_delegated_token(account):
            return None

        # ~ # Get folder id for target
        folder = self.get_folder(account, target)
        if not folder:
            return None
        folderid = folder['@id']

        # Set XML Request
        share_info_request_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
                <session/>
                <account by="name">%s</account>
                <userAgent name="zclient" version="10.0.0_GA_4518"/>
            </context>
        </soap:Header>
        <soap:Body>
            <CreateMountpointRequest xmlns="urn:zimbraMail">
                <link l="%s" name="%s" owner="%s" path="%s"/>
            </CreateMountpointRequest>
        </soap:Body>
        </soap:Envelope>''' % (self.__delegated_token, account, folderid,
                              name, owner, path)

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=share_info_request_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Body/soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return None

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        return True

    def create_account(self, account_info):
        '''
        Create user account
        Returns a boolean according to success or not of the creation
        '''
        # Clear the ZimbraSoap instance variables
        self.__message = ''
        self.__xml_response = ''

        # Set account variables
        try:
            name = account_info['name']
            password = account_info['password']
            givenName = account_info['givenName']
            sn = account_info['sn']
            displayName = account_info['displayName']
        except:
            return False

        # Set XML Request
        create_account_request_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
                <session/>
                <userAgent name="zclient" version="10.0.0_GA_4518"/>
            </context>
        </soap:Header>
        <soap:Body>
            <CreateAccountRequest xmlns="urn:zimbraAdmin" name="%s" password="%s">
                <a n="givenName">%s</a>
                <a n="sn">%s</a>
                <a n="displayName">%s</a>
            </CreateAccountRequest>
        </soap:Body>
        </soap:Envelope>''' % (self.__admin_token, name, password,
                              givenName, sn, displayName)

        # Reencode to be able to use accents
        create_account_request_xml = create_account_request_xml.encode("utf-8").decode("latin-1")

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=create_account_request_xml, headers=headers)

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return False

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        # Set token for the new user
        self.__delegated_token = ''
        self.get_delegated_token(name)

        # Set xml response with content of CreateAccountRequest
        self.__xml_response = r.content

        return self.create_account_export(self.__xml_response)

    def create_account_export(self, xml_string=''):
        '''
        Export informations from create_account xml response
        Returns a dict account informations
        '''
        if not xml_string:
            if self.__xml_response:
                xml_string = self.__xml_response
            else:
                self.__message = 'Error account ID not found.'
                return None

        # Proceed XML
        xmldict = xmltodict.parse(xml_string)
        export = xmldict['soap:Envelope']['soap:Body']["CreateAccountResponse"]['account']

        return export

    def delete_account(self, email):
        '''
        Delete user account
        Returns a boolean according to success or not of the deletion
        '''
        # Get account informations
        infos = self.get_info(email)
        if not infos:
            return None
        account_id = self.get_info_value(email, 'id')
        if not account_id:
            return None

        # Set XML Request
        delete_account_request_xml = '''<?xml version="1.0" ?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
        <soap:Header>
            <context xmlns="urn:zimbra">
                <authToken>%s</authToken>
                <session/>
                <userAgent name="zclient" version="10.0.0_GA_4518"/>
            </context>
        </soap:Header>
        <soap:Body>
            <DeleteAccountRequest xmlns="urn:zimbraAdmin" id="%s"/>
        </soap:Body>
        </soap:Envelope>''' % (self.__admin_token, account_id)

        # Post request
        headers = { 'Content-Type': 'application/soap+xml' }
        r = requests.post(self.__url_api, data=delete_account_request_xml, headers=headers)
        self.__xml_response = r.content

        # Check xml response errors
        namespaces = {
            'soap': 'http://www.w3.org/2003/05/soap-envelope',
        }
        xml_element = etree.fromstring(r.content).find('.//soap:Fault/soap:Reason/soap:Text', namespaces)
        if xml_element != None:
            self.__message = xml_element.text
            return None

        # Set last function label
        self.__last_xml_func_called_successfully = inspect.stack()[0][3]

        return True
