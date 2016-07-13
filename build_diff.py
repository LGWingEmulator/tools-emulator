#!/usr/bin/python
# Creates a combined git log of all changes between to repo manifests
#
#  Usage:
# cd <emulator-repo>/tools/emulator/
# ./build_diff.py <build-id-a> <build-id-b>

import apiclient
import argparse
import httplib2
import io
import oauth2client
import os
import sys
import xml.etree.ElementTree

from apiclient.discovery import build as googleapi
from oauth2client import client
from oauth2client import tools

argparser = argparse.ArgumentParser(parents=[tools.argparser]);
argparser.add_argument("build_lo")
argparser.add_argument("build_hi")
args = argparser.parse_args()

def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Create your own client_secret.json
    https://pantheon.corp.google.com/apis/credentials
    Create credential > OAuth client id > Other > Download JSON

    Returns:
        Credentials, the obtained credential.
    """

    CLIENT_SECRET_FILE = 'client_secret.json'
    APPLICATION_NAME = 'Android Emulator GmsCore Updater'
    SCOPES = 'https://www.googleapis.com/auth/androidbuild.internal'

    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.emu_build_diff')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir, 'credentials.json')

    secret_path = os.path.join(credential_dir, CLIENT_SECRET_FILE)
    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        if not os.path.exists(secret_path):
            print '"{}" is missing.'.format(secret_path)
            print 'Download it from go/emu-drive'
            sys.exit(1)
        flow = client.flow_from_clientsecrets(secret_path, SCOPES)
        flow.user_agent = APPLICATION_NAME
        credentials = tools.run_flow(flow, store, args)
        print('Storing credentials to ' + credential_path)
    return credentials

def get_branch_from_build_id(service, build_id):
    response = service.build().list(
        buildType='submitted',
        buildId=str(build_id),
        maxResults=1,
        fields='builds/branch').execute()
    return response.get('builds',[])[0].get('branch')


def download(service, buildId, branch, target, name, output_path=None):
    buildType = 'submitted'
    attemptId='latest'

    artifact = service.buildartifact().get(
        buildType=buildType,
        buildId=buildId,
        target=target,
        attemptId=attemptId,
        resourceId=name).execute()

    if artifact is None:
        raise FetchArtifactException('Unknown artifact %s/%s/%s/%s',
                                     buildId, target, attemptId, name)

    # Lucky us, we always have the size
    size = artifact['size']

    chunksize = -1
    DEFAULT_CHUNK_SIZE = 20 * 1024 * 1024
    if size >= DEFAULT_CHUNK_SIZE:
        chunksize = DEFAULT_CHUNK_SIZE

    # Just like get, except get_media
    dl_req = service.buildartifact().get_media(
        buildType=buildType,
        buildId=buildId,
        target=target,
        attemptId=attemptId,
        resourceId=name)

    # Make any root directories if needed
    if output_path is None:
        output_path = os.getcwd()
        output = os.path.join(output_path, name)

    root_dir = os.path.dirname(output)
    if root_dir and not os.path.isdir(root_dir):
        os.makedirs(root_dir)

    with io.FileIO(output, mode='wb') as fh:
        downloader = apiclient.http.MediaIoBaseDownload(fh, dl_req,
                                                        chunksize=chunksize)
        done = False
        while not done:
            status, done = downloader.next_chunk()

credentials = get_credentials()
http = credentials.authorize(httplib2.Http())

# API list
# https://developers.google.com/apis-explorer/#p/androidbuildinternal/v1/
service = googleapi('androidbuildinternal', 'v1', http=http)

build_lo = args.build_lo
build_hi = args.build_hi

branch_lo = get_branch_from_build_id(service, build_lo)
branch_hi = get_branch_from_build_id(service, build_hi)

print '{0}@{1}'.format(branch_lo, build_lo);
print '{0}@{1}'.format(branch_hi, build_hi);

repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

def getManifest(branch, buildId):
    manifest = 'manifest_{0}.xml'.format(buildId)
    if not os.path.isfile(manifest):
        download(service, buildId=buildId, branch=branch, target='sdk_tools_linux', name=manifest)
    return manifest

manifestLo = getManifest(branch_lo, build_lo)
manifestHi = getManifest(branch_hi, build_hi)

treeLo = xml.etree.ElementTree.parse(manifestLo)
rootLo = treeLo.getroot()

treeHi = xml.etree.ElementTree.parse(manifestHi)
rootHi = treeHi.getroot()
projectsHi = rootHi.iter('project')

log = "/tmp/build_diff.log"
if os.path.isfile(log):
    os.remove(log)

os.system('repo sync -j8')

command = 'bash -c "('

for project in projectsHi:
    path = project.get('path')
    shaHi = project.get('revision')
    projectLo = rootLo.find("./project/[@path='{}']".format(path))
    if projectLo is None:
        command += 'echo ================== new project {} >> {} &&\n'.format(path, log)
    else:
        shaLo = projectLo.get('revision')
        if shaLo != shaHi:
            command += '(cd {} && git log --no-merges {}..{}) >> {} &&\n'.format(repo + '/' + path, shaLo, shaHi, log)

command += 'true)"'

print command
os.system(command)
os.system('less {}'.format(log))
