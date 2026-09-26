from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from production.youtube_auth import ChannelMismatch, ChannelNotConfigured, channel_preflight, safe_oauth_error, verify_public_upload
from scripts.youtube_oauth_bootstrap import authorization_url


class OAuthSafetyTests(unittest.TestCase):
    ID = 'UC' + 'a' * 22

    def test_secret_redacted_and_provider_codes(self):
        self.assertEqual(safe_oauth_error(RuntimeError({'error':'invalid_grant','refresh_token':'secret'})), 'invalid_grant')
        self.assertEqual(safe_oauth_error(RuntimeError('invalid_client: secret=private')), 'invalid_client')
        self.assertEqual(safe_oauth_error(RuntimeError('secret=private')), 'oauth_refresh_failed')
        self.assertEqual(safe_oauth_error(TimeoutError('secret=private')), 'oauth_network_error')

    def test_expected_channel_is_required(self):
        with patch('production.youtube_auth.authorized_client') as client:
            with self.assertRaises(ChannelNotConfigured):
                channel_preflight(object(), '')
            client.assert_not_called()

    def test_channel_identity(self):
        client = Mock()
        client.channels.return_value.list.return_value.execute.return_value = {
            'items':[{'id':self.ID, 'snippet':{'title':'90+ Gündem'}}]
        }
        with patch('production.youtube_auth.authorized_client',return_value=client):
            self.assertEqual(channel_preflight(object(),self.ID)['title'],'90+ Gündem')
            with self.assertRaises(ChannelMismatch):
                channel_preflight(object(),'UC'+'b'*22)
        self.assertEqual(client.channels.return_value.list.call_args.kwargs,{'part':'id,snippet','mine':True})

    def test_mobile_url_offline_and_consent(self):
        from urllib.parse import urlparse, parse_qs
        query=parse_qs(urlparse(authorization_url('client','https://developers.google.com/oauthplayground')).query)
        self.assertEqual(query['access_type'],['offline'])
        self.assertEqual(query['prompt'],['consent'])
        self.assertIn('youtube.upload',query['scope'][0])
        self.assertIn('youtube.readonly',query['scope'][0])

    def test_public_upload_verification(self):
        client = Mock()
        client.videos.return_value.list.return_value.execute.return_value = {
            'items':[{'id':'real-id','status':{'privacyStatus':'public'}}]}
        with patch('production.youtube_auth.authorized_client',return_value=client):
            self.assertTrue(verify_public_upload(object(),'real-id'))
            client.videos.return_value.list.return_value.execute.return_value['items'][0]['status']['privacyStatus']='private'
            self.assertFalse(verify_public_upload(object(),'real-id'))


if __name__ == '__main__':
    unittest.main()
