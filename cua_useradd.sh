#!/bin/bash
#
################################
# Name: cua_useradd.sh
# Description:
#    Create a Samba-AD user account with its attributes, set its expiration date,
#    add it to different groups and create the Zimbra mail account
# Version: 2024.9.30
# Copyright: 2023-2024, Noël MARTINON
# Licence: GPLv3
################################
#
# This script must be launch on Samba AD DC server.
# For Samba account creation, it uses 'ldbsearch' command, which is a part of Samba4, and do not
# require a credential as the 'ldapsearch' command requires.
# For Zimbra account creation, it uses an external python3 script using SOAP API
#
################################
#
# Example usage :
# cua_useradd.sh -u usertest -f User -s "TEST" -p "PA5#5W0RD!" -m "usertest@domain.tld" -t "Computer technician" -c "The Company" \
# -g "AD_GRP1,AD_GRP2" mobile=0123456789,pager=123,accountExpires=31/12/2024 -w "MAIL_PAS5W0RD+" -d "liste1@domain.tld,liste2@domain.tld" 
#
# NB: The first AD group description is apply to The AD user department
#

# Get current script directory
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# Get settings
source "${SCRIPT_DIR}/cua_config.env"

# Read command line arguments
POSITIONAL=()
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    -u|--username)
      USERNAME="$2"
      shift # past argument
      shift # past value
      ;;
    -s|--surname)
      export SURNAME="$2"
      shift # past argument
      shift # past value
      ;;
    -f|--firstname)
      export FIRSTNAME="$2"
      shift # past argument
      shift # past value
      ;;
    -p|--password)
      PASSWORD="$2"
      shift # past argument
      shift # past value
      ;;
    -m|--mail)
      export MAIL="$2"
      shift # past argument
      shift # past value
      ;;
    -w|--mailpassword)
      export MAILPASSWORD="$2"
      shift # past argument
      shift # past value
      ;;
    -d|--distributionlists) # comma separated values
      DISTRIBLISTS="$2"
      shift # past argument
      shift # past value
      ;;
    -c|--company)
      COMPANY="$2"
      shift # past argument
      shift # past value
      ;;
    -t|--title)
      TITLE="$2"
      shift # past argument
      shift # past value
      ;;
    -o|--ou)
      OU="$2"
      shift # past argument
      shift # past value
      ;;
    -g|--group) # comma separated values, first one becomes primary group
      GROUP="$2"
      shift # past argument
      shift # past value
      ;;
    *)    # unknown option
      POSITIONAL+=("$1") # save it in an array for later
      shift # past argument
      ;;
  esac
done

set -- "${POSITIONAL[@]}" # restore positional parameters

################################
# Display parameters
################################
#~ echo "USERNAME     = ${USERNAME}"
#~ echo "PASSWORD     = ${PASSWORD}"
#~ echo "FIRSTNAME    = ${FIRSTNAME}"
#~ echo "SURNAME      = ${SURNAME}"
#~ echo "MAIL         = ${MAIL}"
#~ echo "MAILPASSWORD = ${MAILPASSORD}"
#~ echo "DISTRIBLISTS = ${DISTRIBLISTS}"
#~ echo "TITLE        = ${TITLE}"
#~ echo "COMPANY      = ${COMPANY}"
#~ echo "OU           = ${OU}"
#~ echo "GROUP        = ${GROUP}"
#~ echo "POSITIONAL   = ${POSITIONAL[@]}"

################################
# Check the required arguments
################################
[ -z "${USERNAME}" ] && echo "ERROR: Empty username" && exit 1
[ -z "${PASSWORD}" ] && echo "ERROR: Empty password" && exit 1
[ -z "${SURNAME}" ] && echo "ERROR: Empty surname" && exit 1
[ -z "${FIRSTNAME}" ] && echo "ERROR: Empty firstname" && exit 1

################################
# Set "OU" and additional groups according to user main group
################################
GROUPS_DONE=0
for i in "${!GROUPS_CN[@]}"; do
    # Set OU to default value ("*" in GROUPS_CN is the default value)
    [[ "${GROUPS_CN[$i]}" == "*" ]] && IFS=''  OU="${GROUPS_OU[$i]}"
    # Set OU and additional groups if required
    if [[ "${GROUPS_CN[$i]}" == "${PRIMARYGROUP}" ]]; then
        IFS=''  OU="${GROUPS_OU[$i]}"
        IFS=',' read -ra values <<< "${GROUPS_ADDITIONAL[$i]}"
        for val in "${values[@]}"; do
            COMPANY_GROUPS+=("${val}")
        done
        GROUPS_DONE=1
    fi
    [ $GROUPS_DONE -eq 1 ] && break
done

################################
# Create user and the home directory
################################
## Create user account
echo "-------- AD account --------"
shopt -s nocasematch
if [[ "${GROUP}" == *"NOSERVICE"* ]]; then
    unset ${LOGON_SCRIPT}
fi
if [ -z "${LOGON_SCRIPT}" ]; then 
    cmd=(samba-tool user create --use-username-as-cn --given-name="${FIRSTNAME}" --surname="${SURNAME}" --mail-address="${MAIL}")
else
    cmd=(samba-tool user create --use-username-as-cn --given-name="${FIRSTNAME}" --surname="${SURNAME}" --mail-address="${MAIL}" --script-path="logon.bat")
fi

[ ! -z "${TITLE}" ] && cmd+=(--job-title="${TITLE}")
[ ! -z "${COMPANY}" ] && cmd+=(--company="${COMPANY}")
[ ! -z "${OU}" ] && cmd+=(--userou="${OU}")
cmd+=("${USERNAME}" "${PASSWORD}")
retcmd=$("${cmd[@]}" 2>&1)
[[ $? -ne 0 ]] && echo "ERROR: Can't create account '${USERNAME}': ${retcmd}" && exit 1
echo $retcmd

################################
# Set user's group(s)
################################
## Add user to group(s)
IFS=',' read -ra values <<< "${GROUP}"
PRIMARYGROUP="${values[0]}"
for val in "${values[@]}"
do
#~ echo "Add user to group '${val}'"
samba-tool group addmembers "${val}" "${USERNAME}"
[[ $? -ne 0 ]] && echo "ERROR: Unable to add user to group '${val}'" && exit 1
done

## Remove "Domain Users" if primary group is NOSERVICE
shopt -s nocasematch
[[ "${PRIMARYGROUP}" == "NOSERVICE" ]] && samba-tool group removemembers "Domain Users" "${USERNAME}"

## Force primary group to "Domain Users" if none
[ -z "${GROUP}" ] && echo "Set primary group to 'Domain Users'" && PRIMARYGROUP="Domain Users"

## Add to company groups if $COMPANY match parameter $COMPANY_NAME
[[ "${COMPANY^^}" == "${COMPANY_NAME}" ]] && for grp in "${COMPANY_GROUPS[@]}"; do samba-tool group addmembers "${grp}" "${USERNAME}"; done

################################
# Assign primary group and set extra attributes (tel, pager, user service text...)
################################
DN=$(ldbsearch -H /var/lib/samba/private/sam.ldb -s sub -b "${BASE_DN}" "(&(cn=${USERNAME})${USER_FILTER})" dn | grep -E '^dn:' | awk '{print $2}')
[ -z "$DN" ] && echo "ERROR: DN not found for user '${USERNAME}'" && exit 1

## Get primary group description to set user department
DEPARTMENT=$(ldbsearch -H /var/lib/samba/private/sam.ldb -s sub -b "${BASE_DN}" "(&(cn=${PRIMARYGROUP})${GROUP_FILTER})" description | grep -E '^description:')
# Base64 decoding if needed
if  [[ "$DEPARTMENT" == "description::"* ]]
then
    DEPARTMENT=$(echo $DEPARTMENT | awk '{print $2}' | base64 -d)
else
    DEPARTMENT=$(echo $DEPARTMENT | awk '{$1=""; print $0}')
fi
[ -z "$DEPARTMENT" ] && echo "ERROR: Empty DESCRIPTION for group '${PRIMARYGROUP}'" && exit 1

## Set the user's departement
echo "Set user's department to '${DEPARTMENT}'"
echo "dn: $DN
changetype: modify
replace: department
department: $DEPARTMENT" > "/tmp/${USERNAME}.ldif"

## Add optional attributes to ldif by splitting argument3 with bash parameter expansion syntax
# (see http://mywiki.wooledge.org/BashFAQ/073?action=show&redirect=ParameterExpansion)
IFS=',' read -ra values <<< "${POSITIONAL[@]}"
for val in "${values[@]}"
do
[ -z "${val}" ] && continue
echo "Set attribute '${val}'"
if [[ "${val%%=*}" == "accountExpires" ]]
then
    EXPIRES=${val#*=}
    EXPIRES_SYS=$(busybox date -D %d/%m/%Y -d "${EXPIRES}" +%F)
    LDAP_TIMESTAMP=$((($(date +%s -d "${EXPIRES_SYS}") + 11644473600 + 60*60*24) * 10000000))
    val="accountExpires=${LDAP_TIMESTAMP}"
fi
cat <<EOF >> "/tmp/${USERNAME}.ldif"
-
replace: ${val%%=*}
${val%%=*}: ${val#*=}
EOF
done

## Apply primary group and extra attributes (tel, pager...)
ldbmodify -H /var/lib/samba/private/sam.ldb "/tmp/${USERNAME}.ldif" >/dev/null 2>&1
[[ $? -ne 0 ]] && echo "ERROR: Unable to apply users's LDIF (primary group and extra attributes)" && exit 1

################################
# Create the user's email
################################
if [ ! -z "${MAIL}" ] && [ ! -z "${MAILPASSWORD}" ]
then
echo "-------- Adresse mél --------"

# Set distributionlist to json format
DISTRIBLISTS_JSON=""
IFS=',' read -ra arr <<< "${DISTRIBLISTS}"
for substr in "${arr[@]}" ; do
  DISTRIBLISTS_JSON=${DISTRIBLISTS_JSON}"\""$substr"\","
done
export DISTRIBLISTS_JSON=${DISTRIBLISTS_JSON::-1}

# Read mail json template by substituting environment variables 
read -r -d '' account_info <<< `envsubst < "${SCRIPT_DIR}/cua_mail_account_info.json"`

# Encode json to base64 
account_info_b64=$(echo -n ${account_info} | base64 -w 0)

# Execute command to create mail account
echo "$(/usr/bin/python3 /opt/cua-samba-ad-zimbra/zimbra_createaccount.py ${account_info_b64})"
else
echo "Processus de création du mail non exécutée"
fi

