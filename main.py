import os
import json

from env import ENV

from loguru import logger as baseLogger
from log_utils import LogUtil

import google_auth_oauthlib.flow
from google.auth.transport.requests import Request
import google_auth_oauthlib.interactive
from google.oauth2.credentials import *
from google.auth.exceptions import *
import googleapiclient.discovery as api_discovery
from googleapiclient.errors import *

ROOT_DIR = os.curdir
scopes = ["https://www.googleapis.com/auth/youtube.readonly"]
client_secrets_file = "client_secret_753681832885-u3jm92fuug14rvoe8mib0fr81petpd89.apps.googleusercontent.com.json"
config_path = os.path.join(ROOT_DIR, "secrets")
test_data_path = os.path.join(ROOT_DIR, "test_data")
# creating a youtubeapi.v3 authenticated resource

# token expiry: 24h
subscriptionResponsePath = os.path.join(
    test_data_path, "SubscriptionsSearchResponse.json")

videoResponsePath = os.path.join(
    test_data_path, "VideosSearchResponse.json")


def fetch_credentials_google() -> Credentials:
    logger = LogUtil.logger
    logger.debug("Opening google Oauth window")
    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
        os.path.join(config_path, client_secrets_file), scopes)
    credentials = flow.run_local_server()
    logger.debug("Retrieved credentials from server")

    with open(os.path.join(config_path, "oath_token.json"), "w") as f:
        logger.debug("Writing credentials locally")
        f.write(credentials.to_json())
    return credentials
# throws DefaultCredentialsError, FileReadError


def fetch_credentials_local() -> Credentials:
    logger = LogUtil.logger
    oath_token = os.path.join(config_path, "oath_token.json")

    with open(oath_token) as token:
        logger.debug(f"Reading credentials from {oath_token}")
        creds = Credentials.from_authorized_user_file(oath_token, scopes)
        logger.debug(f"Successfully read credentials {oath_token}")
        return creds


@baseLogger.catch
def main():
    # disables OAuth https verification -- for local use
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    api_service_name = "youtube"
    api_version = "v3"
    logger = LogUtil.configure(baseLogger)

    # -------------- Google Oauth ----------------#
    try:
        logger.debug("Fetching local credentials")
        credentials = fetch_credentials_local()
    except (FileNotFoundError) as err:
        logger.debug(
            "File not found - fetching with Google OAuth2 API")
        credentials = fetch_credentials_google()

    try:
        if credentials and not credentials.valid:
            logger.debug(
                "Invalid credentials")
            logger.debug(
                "Attempting Refresh")
            credentials.refresh(Request())
            logger.debug(
                "Refresh Successful")
            with open(os.path.join(config_path, "oath_token.json"), "w") as f:
                logger.debug("Writing credentials locally")
                f.write(credentials.to_json())

    except RefreshError as err:
        # renew - expired token
        logger.debug(err)
        credentials = fetch_credentials_google()

    # ------------ Youtube API ------------------#

    youtube = api_discovery.build(
        api_service_name, api_version, credentials=credentials)

    # useful for inspecting the api client
    # print(youtube.__dir__())

    if ENV != "LOCAL":
        try:
            subs = youtube.subscriptions().list(part="contentDetails, id, snippet",
                                                mine=True, maxResults=50, order="alphabetical").execute()
        except HttpError as err:
            logger.error(err)
            subs = {}
    else:
        try:
            with open(subscriptionResponsePath, "r") as f:
                subs = json.load(f)
        except IOError as err:
            logger.error(err)
            subs = {}

    logger.debug("Logging sub data:", subs)

    # translate subs to list of (subIds, newItemCount)
    subData: list = subs.get("items")
    logger.debug("Logging item data", data=subData)
    # translate
    # could've just done a list comprehension here but wanted to make a higher order func
    # to test knowledge

    def subsWithNewItems(subDataEle):
        return {"channelId": subDataEle.get("snippet").get("resourceId").get('channelId'), "newItemCount": subDataEle.get(
                "contentDetails").get("newItemCount")}

    newItems: list[dict] = subData and list(map(subsWithNewItems, subData))
    logger.debug(f"{len(newItems or [])} channels fetched.")
    # filter
    newItems = [i for i in newItems or [] if i.get("newItemCount") > 0]
    logger.debug(f"{len(newItems)} channels with new videos")
    logger.debug("Subscribed channels fetched", data=newItems)
    # perform search for each subId
    # for item in newItems:
    # rework to do this async
    # order by recent date uploaded, limit of newItemCount
    newVideos = {}
    for item in newItems or []:
        # we'll want to store more info about the channel (like author name, description, etc)
        # here once we've modeled out our schema.
        if ENV != "LOCAL":
            try:
                videos = youtube.search().list(channelId=item.get('channelId'), part='snippet', type='video', maxResults=item.get(
                    'newItemCount'), order='date').execute()
                newVideos[item.get('channelId')] = videos
                logger.debug("videos retrived from search.list",
                             data=newVideos)

            except HttpError as err:
                logger.error(err)
                videos = {}
        else:
            try:
                with open(videoResponsePath, "r") as f:
                    videos = json.load(f)
            except IOError as err:
                logger.error(err)
                videos = {}

        # TODO: ytdl requests here
    # this will fetch mp3 data for each video returned in our search
    # should: be async, use an exponential failover alg (retries=5: 1s,2s,4s,8s,16s)
    # if fail, persist failed video request as: not retrieved | not watched
    # if success, store it in the local file system; persist as : retrieved|not watched

    # TODO: implement a way to specify which channels we want to get upload updates on
    # the backend will add these to a notify list. this list will be used to publish the mp3 files the user is interested in
if __name__ == "__main__":
    main()
