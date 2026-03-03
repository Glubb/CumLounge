"""Tests for input validation utilities."""
import unittest
from src.validation import (
    sanitize_text, 
    sanitize_username, 
    validate_duration_string,
    validate_config
)


class TestSanitizeText(unittest.TestCase):
    
    def test_normal_text(self):
        result = sanitize_text("Hello world")
        self.assertEqual(result, "Hello world")
    
    def test_text_with_newlines(self):
        result = sanitize_text("Line 1\nLine 2")
        self.assertEqual(result, "Line 1\nLine 2")
    
    def test_max_length(self):
        long_text = "a" * 1000
        result = sanitize_text(long_text, max_length=100)
        self.assertEqual(len(result), 100)
    
    def test_control_characters_removed(self):
        text_with_control = "Hello\x00\x01World"
        result = sanitize_text(text_with_control)
        self.assertEqual(result, "HelloWorld")
    
    def test_empty_string(self):
        result = sanitize_text("")
        self.assertIsNone(result)
    
    def test_whitespace_only(self):
        result = sanitize_text("   \n\t  ")
        self.assertIsNone(result)
    
    def test_none_input(self):
        result = sanitize_text(None)
        self.assertIsNone(result)


class TestSanitizeUsername(unittest.TestCase):
    
    def test_valid_username(self):
        result = sanitize_username("john_doe")
        self.assertEqual(result, "john_doe")
    
    def test_username_with_at(self):
        result = sanitize_username("@john_doe")
        self.assertEqual(result, "john_doe")
    
    def test_uppercase_converted(self):
        result = sanitize_username("JohnDoe")
        self.assertEqual(result, "johndoe")
    
    def test_invalid_characters(self):
        result = sanitize_username("john-doe")
        self.assertIsNone(result)
    
    def test_too_long(self):
        result = sanitize_username("a" * 50)
        self.assertIsNone(result)
    
    def test_empty_string(self):
        result = sanitize_username("")
        self.assertIsNone(result)


class TestValidateDurationString(unittest.TestCase):
    
    def test_valid_single_unit(self):
        self.assertTrue(validate_duration_string("1h"))
        self.assertTrue(validate_duration_string("30m"))
        self.assertTrue(validate_duration_string("2d"))
    
    def test_valid_multiple_units(self):
        self.assertTrue(validate_duration_string("1h 30m"))
        self.assertTrue(validate_duration_string("2d 3h"))
    
    def test_with_spaces(self):
        self.assertTrue(validate_duration_string("  1h  30m  "))
    
    def test_invalid_format(self):
        self.assertFalse(validate_duration_string("abc"))
        self.assertFalse(validate_duration_string("1x"))
    
    def test_empty_string(self):
        self.assertFalse(validate_duration_string(""))


class TestValidateConfig(unittest.TestCase):
    
    def test_valid_config(self):
        config = {
            "bot_token": "123456:ABC-DEF",
            "database": ["sqlite", "/path/to/db.sqlite"],
            "karma_amount_add": 2,
            "reg_open": True
        }
        errors = validate_config(config)
        self.assertEqual(errors, [])
    
    def test_missing_bot_token(self):
        config = {}
        errors = validate_config(config)
        self.assertIn("bot_token is required", errors)
    
    def test_invalid_karma_amount(self):
        config = {
            "bot_token": "test",
            "karma_amount_add": 200  # Too high
        }
        errors = validate_config(config)
        self.assertTrue(any("karma_amount_add" in e for e in errors))
    
    def test_invalid_database_config(self):
        config = {
            "bot_token": "test",
            "database": ["invalid_type", "/path"]
        }
        errors = validate_config(config)
        self.assertTrue(any("database type" in e for e in errors))


if __name__ == '__main__':
    unittest.main()
