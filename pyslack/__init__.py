import datetime
import logging
import requests


class SlackError(Exception):
    pass


class SlackClient(object):

    BASE_URL = 'https://slack.com/api'

    def __init__(self, token):
        self.token = token
        self.channels = {}
        self.ul_by_id = {}
        self.ul_by_name = {}
        self.blocked_until = None
        self.channel_name_id_map = {}

    def setup_cache(self, force_refresh=False):
        """
        Create a cache to reduce requests for users and channels
        User force_referesh=True to rebuild it
        """
        if force_refresh or not self.ul_by_id:
            self.update_user_lists_dicts()
        if force_refresh or not self.channels:
            self.update_channel_lists_dict()

    def _channel_is_name(self, channel):
        return channel.startswith('#')

    def _make_request(self, method, params, disable_cert_verification=False):
        """Make request to API endpoint
           Specify disable_cert_verification=True to skip verifying certs
        """
        if self.blocked_until is not None and \
                datetime.datetime.utcnow() < self.blocked_until:
            raise SlackError("Too many requests - wait until {0}"
                             .format(self.blocked_until))

        url = "%s/%s" % (SlackClient.BASE_URL, method)
        params['token'] = self.token
        response = requests.post(url, data=params, verify=disable_cert_verification)

        if response.status_code == 429:
            # Too many requests
            retry_after = int(response.headers.get('retry-after', '1'))
            self.blocked_until = datetime.datetime.utcnow() +\
                datetime.timedelta(seconds=retry_after)
            raise SlackError("Too many requests - retry after {0} second(s)"
                             .format(retry_after))

        result = response.json()
        if not result['ok']:
            raise SlackError(result['error'])
        return result

    def channels_list(self, exclude_archived=True, **params):
        """channels.list
        This method returns a list of all channels in the team. This includes
        channels the caller is in, channels they are not currently in, and
        archived channels. The number of (non-deactivated) members in each
        channel is also returned.
        https://api.slack.com/methods/channels.list
        """
        method = 'channels.list'
        params.update({'exclude_archived': exclude_archived and 1 or 0})
        return self._make_request(method, params)

    def channel_name_to_id(self, channel_name, force_lookup=False):
        """Helper name for getting a channel's id from its name
        """
        if force_lookup or not self.channel_name_id_map:
            channels = self.channels_list()['channels']
            self.channel_name_id_map =\
                {channel['name']: channel['id'] for channel in channels}
        channel = channel_name.startswith('#') \
            and channel_name[1:] or channel_name
        return self.channel_name_id_map.get(channel)

    def chat_post_message(self, channel, text, **params):
        """chat.postMessage

        This method posts a message to a channel.

        https://api.slack.com/methods/chat.postMessage
        """
        method = 'chat.postMessage'

        params.update({
            'channel': self.channel_name_to_id(channel),
            'text': text,
        })

        return self._make_request(method, params)

    def chat_delete(self, channel, ts, **params):
        """chat.delete

        Deletes a message by timestamp
        https://api.slack.com/methods/chat.delete
        """

        method = 'chat.delete'
        params.update({
            'channel': self.channel_name_to_id(channel),
            'ts': ts,
        })

        return self._make_request(method, params)

    def chat_update(self, channel, ts, text, **params):
        """chat.update

        Updates a message by timestamp
        https://api.slack.com/methods/chat.update
        """

        method = 'chat.update'
        params.update({
            'channel': self.channel_name_to_id(channel),
            'ts': ts,
            'text': text,
        })

        return self._make_request(method, params)

    def channel_history(self, channel, count=10, do_prettify=True, **params):
        """channels.history

        This method gets the history for a particular channel
        https://api.slack.com/methods/channels.history
        """

        self.setup_cache()

        # Verify count is between 1 and 1000 per Slack documentation
        if count < 1 or count > 1000:
            raise SlackError("count parameter out of range (must be 1-1000)")

        method = 'channels.history'

        params.update({
            'channel': self.channel_name_to_id(channel),
            'count': count,
        })

        ret = self._make_request(method, params)

        if do_prettify:
            for u in ret['messages']:
                if 'user' in u:
                    u['user'] = self.ul_by_id[u['user']]

        return ret

    def channel_list(self, exclude_archived="1", **params):
        """channels.list

        Gets a list of channels
        https://api.slack.com/methods/channels.list
        """
        method = 'channels.list'

        params.update({
            'exclude_archived': exclude_archived,
        })

        return self._make_request(method, params)

    def update_channel_lists_dict(self):
        """Updates the channel list dict"""

        channel_list_ = self.channel_list(exclude_archived=0)
        for channel_ in channel_list_['channels']:
            self.channels[channel_['name']] = channel_

    def users_list(self, **params):
        """users.list

        Gets a list of users
        https://api.slack.com/methods/users.list
        """
        method = 'users.list'

        return self._make_request(method, params)

    def update_user_lists_dicts(self):
        """updates the user list dictionary to avoid repeated queries"""

        user_list_ = self.users_list()
        for user_ in user_list_['members']:
            self.ul_by_id[user_['id']] = user_
            self.ul_by_name[user_['name']] = user_

        # Special Slackbottery
        self.ul_by_id[u'USLACKBOT'] = {u'status': None, u'profile': {},
                                       u'name': 'Slackbot'}

    def auth_test(self, **params):
        """auth.test

        Performs test of authentication
        https://api.slack.com/methods/auth.test
        """

        method = "auth.test"
        return self._make_request(method, params)

    def channels_info(self, channel, **params):
        """channels.info

        Gets info for a channel
        https://api.slack.com/methods/channels.info
        """

        method = 'channels.info'
        params.update({
            'channel': self.channel_name_to_id(channel)
        })
        return self._make_request(method, params)

    def channels_invite(self, channel, user, **params):
        """channels.invite

        Invite a user to a channel
        https://api.slack.com/methods/channels.invite
        """

        self.setup_cache()

        method = 'channels.invite'
        params.update({
            'channel': self.channel_name_to_id(channel),
            'user': self.ul_by_name[user]['id']
        })

        return self._make_request(method, params)

    def channels_join(self, channel, **params):
        """channels.join

        Joins a channel
        https://api.slack.com/methods/channels.join
        """

        method = 'channels.join'
        params.update({
            'name': self.channel_name_to_id(channel),
        })

        return self._make_request(method, params)

    def channels_leave(self, channel, **params):
        """channels.leave

        Joins a channel
        https://api.slack.com/methods/channels.leave
        """

        method = 'channels.leave'
        params.update({
            'channel': self.channel_name_to_id(channel),
        })

        return self._make_request(method, params)

    def channels_mark(self, channel, ts, **params):
        """channels.mark

        Moves the read curser in a channel
        https://api.slack.com/methods/channels.mark
        """

        method = 'channels.mark'
        params.update({
            'channel': self.channel_name_to_id(channel),
            'ts': ts,
        })

        return self._make_request(method, params)

    def channels_setPurpose(self, channel, purpose, **params):
        """channels.setPurpose

        Set the purpose of a channel
        https://api.slack.com/methods/channels.setPurpose
        """

        method = 'channels.setPurpose'
        params.update({
            'channel': self.channel_name_to_id(channel),
            'purpose': purpose,
        })

        return self._make_request(method, params)

    def channels_setTopic(self, channel, topic, **params):
        """channels.setTopic

        Sets the topic for a channel
        https://api.slack.com/methods/channels.setTopic
        """

        method = 'channels.setTopic'
        params.update({
            'channel': self.channel_name_to_id(channel),
            'topic': topic,
        })

        return self._make_request(method, params)

    def emoji_list(self, **params):
        """emoji.list

        Get the list of emojis
        https://api.slack.com/methods/emoji.list
        """

        method = 'emoji.list'

        return self._make_request(method, params)

    def stars_list(self, user, count=100, page=1, **params):
        """stars.list

        Get list of all stars by user
        https://api.slack.com/methods/stars.list
        """

        self.setup_cache()

        method = 'stars.list'

        params.update({
            'user': self.ul_by_name[user]['id'],
            'count': count,
            'page': page,
        })

        return self._make_request(method, params)

    def chat_update_message(self, channel, text, timestamp, **params):
        """chat.update

        This method updates a message.

        Required parameters:
            `channel`: Channel containing the message to be updated. (e.g: "C1234567890")
            `text`: New text for the message, using the default formatting rules. (e.g: "Hello world")
            `timestamp`:  Timestamp of the message to be updated (e.g: "1405894322.002768")

        https://api.slack.com/methods/chat.update
        """
        method = 'chat.update'
        if self._channel_is_name(channel):
            # chat.update only takes channel ids (not channel names)
            channel = self.channel_name_to_id(channel)
        params.update({
            'channel': channel,
            'text': text,
            'ts': timestamp,
        })
        return self._make_request(method, params)


class SlackHandler(logging.Handler):
    """A logging handler that posts messages to a Slack channel!

    References:
    http://docs.python.org/2/library/logging.html#handler-objects
    """
    def __init__(self, token, channel, **kwargs):
        super(SlackHandler, self).__init__()
        self.client = SlackClient(token)
        self.channel = channel
        self._kwargs = kwargs

    def emit(self, record):
        message = self.format(record)
        self.client.chat_post_message(self.channel,
                                      message,
                                      **self._kwargs)
