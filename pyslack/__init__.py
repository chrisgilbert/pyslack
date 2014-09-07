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
        self.update_channel_lists_dict()
        self.update_user_lists_dicts()

    def _make_request(self, method, params):
        """Make request to API endpoint

        Note: Ignoring SSL cert validation due to intermittent failures
        http://requests.readthedocs.org/en/latest/user/advanced/#ssl-cert-verification
        """
        url = "%s/%s" % (SlackClient.BASE_URL, method)
        params['token'] = self.token
        result = requests.post(url, data=params, verify=False).json()
        if not result['ok']:
            raise SlackError(result['error'])
        return result

    def channelname_to_channelid(self, channelname, update_channel_list=True):
        tries = 0

        if channelname[0] == 'C':
            return channelname

        while tries < 1:
            if channelname in self.channels:
                return self.channels[channelname]['id']
            else:
                if tries == 0 and update_channel_list is True:
                    self.update_channel_lists_dict()
                elif tries != 0:
                    raise SlackError("channel not found")

            tries += 1



    def chat_post_message(self, channel, text, username="cirtbot", **params):
        """chat.postMessage

        This method posts a message to a channel.

        Check docs for all available **params options:
        https://api.slack.com/methods/chat.postMessage
        """
        method = 'chat.postMessage'

        params.update({
            'channel': self.channelname_to_channelid(channel),
            'text': text,
            'username': username
        })

        return self._make_request(method, params)

    def chat_delete(self, channel, ts, **params):
        """chat.delete

        Deletes a message by timestamp
        https://api.slack.com/methods/chat.delete
        """

        method = 'chat.delete'
        params.update({
            'channel': self.channelname_to_channelid(channel),
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
            'channel': self.channelname_to_channelid(channel),
            'ts': ts,
            'text': text,
        })

        return self._make_request(method, params)

    def channel_history(self, channel, count=10, do_prettify=True, **params):
        """channels.history

        This method gets the history for a particular channel
        https://api.slack.com/methods/channels.history
        """

        # Verify count is between 1 and 1000 per Slack documentation
        if count < 1 or count > 1000:
            raise SlackError("count parameter out of range (must be 1-1000)")

        method = 'channels.history'

        params.update({
            'channel': self.channelname_to_channelid(channel),
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

        cl = self.channel_list(exclude_archived=0)
        for c in cl['channels']:
            self.channels[c['name']] = c

    def users_list(self, **params):
        """users.list

        Gets a list of users
        https://api.slack.com/methods/users.list
        """
        method = 'users.list'

        return self._make_request(method, params)

    def update_user_lists_dicts(self):
        """updates the user list dictionary to avoid repeated queries"""

        ul = self.users_list()
        for u in ul['members']:
            self.ul_by_id[u['id']] = u
            self.ul_by_name[u['name']] = u

        # Special Slackbottery
        self.ul_by_id[u'USLACKBOT'] = {u'status': None, u'profile':{}, u'name': 'Slackbot'}

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
            'channel' : self.channelname_to_channelid(channel)
        })
        return self._make_request(method, params)

    def channels_invite(self, channel, user, **params):
        """channels.invite

        Invite a user to a channel
        https://api.slack.com/methods/channels.invite
        """

        method = 'channels.invite'
        params.update({
            'channel': self.channelname_to_channelid(channel),
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
            'name': self.channelname_to_channelid(channel),
        })

        return self._make_request(method, params)

    def channels_leave(self, channel, **params):
        """channels.leave

        Joins a channel
        https://api.slack.com/methods/channels.leave
        """

        method = 'channels.leave'
        params.update({
            'channel': self.channelname_to_channelid(channel),
        })

        return self._make_request(method, params)

    def channels_mark(self, channel, ts, **params):
        """channels.mark

        Moves the read curser in a channel
        https://api.slack.com/methods/channels.mark
        """

        method = 'channels.mark'
        params.update({
            'channel': self.channelname_to_channelid(channel),
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
            'channel': self.channelname_to_channelid(channel),
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
            'channel': self.channelname_to_channelid(channel),
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

    def stars_list(self, user, count=100, page=1, **params ):
        """stars.list

        Get list of all stars by user
        https://api.slack.com/methods/stars.list
        """

        method = 'stars.list'

        params.update({
            'user': self.ul_by_name[user]['id'],
            'count': count,
            'page': page,
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
