#!/usr/bin/env python3
###############################################################################
# ZimbraSoap example - Create user account and apply it some settings         #
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

import sys
import base64
import json
from pathlib import Path
import xml.dom.minidom
from zimbrasoap import ZimbraSoap


def main():
    try:
        if len(sys.argv) < 1:
            print('Erreur les paramètres json du compte sont manquants')
            exit(1)
        try:
            account_info = json.loads(base64.b64decode(sys.argv[1]))
            print(json.dumps(account_info, indent=2))
        except:
            print('Erreur de chargement des paramètres json du compte')
            exit(1)

        config_file = 'zimbra_config.json'
        if not Path(config_file).is_file():
            config_file = 'inc/'+config_file

        with open(config_file, 'r') as jsonfile:
            config = json.load(jsonfile)

        email = account_info['name']

        try:
            # Init connection
            zs = ZimbraSoap(config['url'], config['admin_username'], config['admin_password'])
        except:
            print('Erreur impossible de se connecter au serveur Zimbra')
            exit(1)


        # ~ # Delete account
        # ~ isAccountDeleted = zs.delete_account(email)
        # ~ if (isAccountDeleted):
            # ~ print('Account %s deleted' % (email))

        # Create account
        try:
            if zs.get_info(email):
                print('Le compte %s existe déjà' % (email))
            else:
                isAccountCreated = zs.create_account(account_info)
                if isAccountCreated:
                    print('Compte %s créé' % (email))
                else:
                    print('Erreur en créant le compte %s: %s' % (account_info['name'], zs.get_message()))
        except:
            print('Erreur impossible de créer le compte %s' % (email))
            exit(1)


        # Share calendar
        try:
            for calendar in account_info['calendar']:
                if zs.folder_action_share(email, calendar['folder'], calendar['shareEmail'], calendar['granteeType'], calendar['perm']):
                    print('Agenda "%s" partagé' % (calendar['folder']))
                else:
                    print('Erreur en partageant "%s" à "%s" : %s' % (calendar['folder'], email, zs.get_message()))
        except:
            print('Erreur impossible de partager l\'agenda de %s' % (email))
            exit(1)

        # Set account prefs
        try:
            prefs_list = {'zimbraPrefTimeZoneId':'America/Guyana','zimbraPrefComposeFormat':'html'}
            if zs.modify_prefs(email, prefs_list):
                print('Préférences appliquées')
            else:
                print('Erreur d\'application des préférences : %s' % (zs.get_message()))
        except:
            print('Erreur impossible d\'appliquer les préférences ("GMT-4" et "Format mail html"')
            pass

        # Set signature
        try:
            account_signature = {}
            account_signature['name'] = account_info['signature']['name']
            account_signature['type'] = account_info['signature']['type']
            account_signature['checkContent'] = account_info['signature']['checkContent']
            r = requests.post(account_info['signature']['url'])
            account_signature['content'] = r.content.decode("utf-8")
            if account_signature['checkContent'] in account_signature['content']:
                isSignatureCreatedOrModified = zs.modify_signature(email, account_signature, True)
                if isSignatureCreatedOrModified:
                    print('Signature créée')

                    # Apply signature settings on identity
                    signature = zs.get_signature(email, account_signature['name'])
                    identity_list = {
                        'zimbraPrefForwardReplyFormat':'html',
                        'zimbraPrefDefaultSignatureId':'%s' % (signature['@id']),
                        'zimbraPrefForwardReplySignatureId':'%s' % (signature['@id']),
                        'zimbraPrefMailSignatureStyle':'outlook'}
                    isIdentityModified = zs.modify_identity(email, 'DEFAULT', identity_list)
                    if isIdentityModified:
                        print('Signature appliquée')
                    else:
                        print('Erreur d\'application de la signature : %s' % (zs.get_message()))

                    # Show signature content
                    # ~ content = signature['content']['#text']
                    # ~ print(content)
                else:
                    print('Erreur de création de signature : %s' % (zs.get_message()))
            else:
                print('Erreur impossible d\'obtenir la signature')

        except:
            print('Erreur impossible de créer ou apposer la signature')
            pass

        # Add account to distribution list
        for dl_name in account_info['memberofList']:
            try:
                isMemberAdded = zs.add_distribution_listmember(dl_name, email)
                if isMemberAdded:
                    print('Compte ajouté à la liste de distribution "%s"' % (dl_name))
                else:
                    print('Erreur lors de l\'ajout à la liste de distribution "%s" : %s' % (dl_name, zs.get_message()))
            except:
                print('Erreur impossible d\'ajouter à la liste de distribution "%s"' % (dl_name))
                continue

        # Add folder link
        for link in account_info['link']:
            try:
                isLinkCreated = zs.create_mountpoint(email, link['target'], link['name'], link['ownerEmail'], link['folderPath'])
                if isLinkCreated:
                    print('Partage "%s" ajouté' % (link['name']))
                else:
                    print('Erreur lors de la création de "%s" : %s' % (link['name'], zs.get_message()))
            except:
                print('Erreur impossible d\'ajouter le partage "%s"' % (link['name']))
                continue

        # Search and delete emails
        try:
            isMsgCleaned = zs.msg_action_delete(email, 'in:inbox is:unread subject:"Partage créé"')
            if isMsgCleaned:
                print('Emails nettoyés')
            else:
                print('Erreur lors du nettoyage des emails : %s' % (zs.get_message()))
        except:
            print('Erreur impossible de nettoyer les emails')
            pass

    except:
        print('Erreur d\'exécution générale')
        # ~ pass
        raise

if __name__ == '__main__':
    main()
