"""Tests for User model."""
import unittest
from datetime import datetime, timedelta
from src.database import User
from src.globals import RANKS


class TestUser(unittest.TestCase):
    
    def setUp(self):
        """Create a test user before each test."""
        self.user = User()
        self.user.defaults()
        self.user.id = 12345
        self.user.username = "testuser"
        self.user.realname = "Test User"
    
    def test_defaults(self):
        """Test default values are set correctly."""
        user = User()
        user.defaults()
        self.assertEqual(user.rank, RANKS.user)
        self.assertEqual(user.warnings, 0)
        self.assertEqual(user.karma, 0)
        self.assertFalse(user.hideKarma)
        self.assertFalse(user.debugEnabled)
    
    def test_is_joined(self):
        """Test isJoined method."""
        self.assertTrue(self.user.isJoined())
        self.user.left = datetime.now()
        self.assertFalse(self.user.isJoined())
    
    def test_is_blacklisted(self):
        """Test isBlacklisted method."""
        self.assertFalse(self.user.isBlacklisted())
        self.user.rank = RANKS.banned
        self.assertTrue(self.user.isBlacklisted())
    
    def test_is_in_cooldown(self):
        """Test isInCooldown method."""
        self.assertFalse(self.user.isInCooldown())
        
        # Set cooldown in future
        self.user.cooldownUntil = datetime.now() + timedelta(hours=1)
        self.assertTrue(self.user.isInCooldown())
        
        # Set cooldown in past
        self.user.cooldownUntil = datetime.now() - timedelta(hours=1)
        self.assertFalse(self.user.isInCooldown())
    
    def test_obfuscated_id_format(self):
        """Test obfuscated ID format."""
        oid = self.user.getObfuscatedId()
        self.assertIsNotNone(oid)
        self.assertEqual(len(oid), 4)
        # Should only contain valid characters
        valid_chars = "0123456789abcdefghijklmnopqrstuv"
        self.assertTrue(all(c in valid_chars for c in oid))
    
    def test_obfuscated_karma(self):
        """Test obfuscated karma is within expected range."""
        self.user.karma = 100
        obfuscated = self.user.getObfuscatedKarma()
        # Should be within ~20% of actual karma (with some randomness)
        # Allow slightly wider range due to rounding
        self.assertGreaterEqual(obfuscated, 78)
        self.assertLessEqual(obfuscated, 122)
    
    def test_formatted_name_with_username(self):
        """Test formatted name when username exists."""
        name = self.user.getFormattedName()
        self.assertEqual(name, "@testuser")
    
    def test_formatted_name_without_username(self):
        """Test formatted name when username is None."""
        self.user.username = None
        name = self.user.getFormattedName()
        self.assertEqual(name, "Test User")
    
    def test_set_blacklisted(self):
        """Test setBlacklisted method."""
        reason = "Spam"
        self.user.setBlacklisted(reason)
        self.assertEqual(self.user.rank, RANKS.banned)
        self.assertEqual(self.user.blacklistReason, reason)
        self.assertIsNotNone(self.user.left)
    
    def test_add_warning(self):
        """Test addWarning method."""
        cooldown = self.user.addWarning()
        self.assertEqual(self.user.warnings, 1)
        self.assertIsNotNone(self.user.cooldownUntil)
        self.assertIsNotNone(self.user.warnExpiry)
        self.assertIsInstance(cooldown, timedelta)
    
    def test_remove_warning(self):
        """Test removeWarning method."""
        self.user.warnings = 2
        self.user.warnExpiry = datetime.now() + timedelta(hours=1)
        
        self.user.removeWarning()
        self.assertEqual(self.user.warnings, 1)
        self.assertIsNotNone(self.user.warnExpiry)
        
        self.user.removeWarning()
        self.assertEqual(self.user.warnings, 0)
        self.assertIsNone(self.user.warnExpiry)
    
    def test_set_joined(self):
        """Test setJoined method."""
        self.user.rank = RANKS.banned
        self.user.blacklistReason = "Test"
        self.user.left = datetime.now()
        
        self.user.setJoined()
        self.assertEqual(self.user.rank, RANKS.user)
        self.assertIsNone(self.user.blacklistReason)
        self.assertIsNone(self.user.left)


if __name__ == '__main__':
    unittest.main()
