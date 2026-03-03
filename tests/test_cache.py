"""Tests for cache functionality."""
import unittest
from datetime import datetime, timedelta
from src.cache import CachedMessage, Cache


class TestCachedMessage(unittest.TestCase):
    
    def setUp(self):
        """Create a test cached message before each test."""
        self.cm = CachedMessage(user_id=12345)
    
    def test_initialization(self):
        """Test cached message initialization."""
        self.assertEqual(self.cm.user_id, 12345)
        self.assertIsInstance(self.cm.time, datetime)
        self.assertFalse(self.cm.warned)
        self.assertEqual(len(self.cm.upvoted), 0)
        self.assertEqual(len(self.cm.downvoted), 0)
    
    def test_is_expired(self):
        """Test expiration check."""
        # Fresh message should not be expired
        self.assertFalse(self.cm.isExpired())
        
        # Old message should be expired
        self.cm.time = datetime.now() - timedelta(hours=49)
        self.assertTrue(self.cm.isExpired())
    
    def test_upvote_tracking(self):
        """Test upvote tracking."""
        from src.database import User
        user = User()
        user.id = 999
        
        self.assertFalse(self.cm.hasUpvoted(user))
        self.cm.addUpvote(user)
        self.assertTrue(self.cm.hasUpvoted(user))
    
    def test_downvote_tracking(self):
        """Test downvote tracking."""
        from src.database import User
        user = User()
        user.id = 999
        
        self.assertFalse(self.cm.hasDownvoted(user))
        self.cm.addDownvote(user)
        self.assertTrue(self.cm.hasDownvoted(user))


class TestCache(unittest.TestCase):
    
    def setUp(self):
        """Create a test cache before each test."""
        self.cache = Cache()
    
    def test_assign_message_id(self):
        """Test message ID assignment."""
        cm1 = CachedMessage(user_id=123)
        cm2 = CachedMessage(user_id=456)
        
        msid1 = self.cache.assignMessageId(cm1)
        msid2 = self.cache.assignMessageId(cm2)
        
        self.assertIsInstance(msid1, int)
        self.assertIsInstance(msid2, int)
        self.assertNotEqual(msid1, msid2)
    
    def test_save_and_lookup_mapping(self):
        """Test saving and looking up message mappings."""
        uid = 12345
        msid = 100
        message_id = 999
        
        self.cache.saveMapping(uid, msid, message_id)
        
        # Lookup by msid
        result = self.cache.lookupMapping(uid, msid=msid)
        self.assertEqual(result, message_id)
        
        # Lookup by message_id
        result = self.cache.lookupMappingByData(message_id, uid=uid)
        self.assertEqual(result, msid)
    
    def test_get_message(self):
        """Test retrieving cached message."""
        cm = CachedMessage(user_id=123)
        msid = self.cache.assignMessageId(cm)
        
        retrieved = self.cache.getMessage(msid)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.user_id, 123)
    
    def test_get_messages_by_user(self):
        """Test retrieving all messages from a user."""
        user_id = 12345
        
        cm1 = CachedMessage(user_id=user_id)
        cm2 = CachedMessage(user_id=user_id)
        cm3 = CachedMessage(user_id=99999)
        
        msid1 = self.cache.assignMessageId(cm1)
        msid2 = self.cache.assignMessageId(cm2)
        msid3 = self.cache.assignMessageId(cm3)
        
        messages = self.cache.getMessages(user_id)
        self.assertEqual(len(messages), 2)
        
        msids = [msid for msid, cm in messages]
        self.assertIn(msid1, msids)
        self.assertIn(msid2, msids)
        self.assertNotIn(msid3, msids)


if __name__ == '__main__':
    unittest.main()
