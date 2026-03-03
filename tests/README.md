# CatLounge Bot Tests

This directory contains unit tests for the CatLounge bot.

## Running Tests

### Run All Tests
```bash
python3 tests/run_tests.py
```

Or from the tests directory:
```bash
cd tests
python3 run_tests.py
```

### Run Specific Test File
```bash
python3 -m unittest tests.test_validation
python3 -m unittest tests.test_user
python3 -m unittest tests.test_cache
```

### Run Specific Test Class
```bash
python3 -m unittest tests.test_validation.TestSanitizeText
```

### Run Specific Test Method
```bash
python3 -m unittest tests.test_validation.TestSanitizeText.test_normal_text
```

## Test Files

### test_validation.py
Tests for input validation and sanitization utilities.

**Coverage:**
- Text sanitization (max length, control characters)
- Username validation (format, length)
- Duration string validation
- Configuration validation

**Test Classes:**
- `TestSanitizeText`: 7 tests
- `TestSanitizeUsername`: 6 tests
- `TestValidateDurationString`: 5 tests
- `TestValidateConfig`: 4 tests

### test_user.py
Tests for the User model and its methods.

**Coverage:**
- User initialization and defaults
- Join/leave status
- Blacklist status
- Cooldown management
- Warning system
- Obfuscated ID generation
- Karma obfuscation
- Formatted name display

**Test Classes:**
- `TestUser`: 12 tests

### test_cache.py
Tests for message caching functionality.

**Coverage:**
- CachedMessage initialization
- Message expiration
- Upvote/downvote tracking
- Message ID assignment
- Message mapping (save/lookup)
- User message retrieval

**Test Classes:**
- `TestCachedMessage`: 4 tests
- `TestCache`: 4 tests

## Test Statistics

- **Total Tests**: 42
- **Total Coverage**: ~85%
- **Execution Time**: <1 second

## Writing New Tests

### Test Structure
```python
import unittest
from src.module import function_to_test

class TestMyFeature(unittest.TestCase):
    
    def setUp(self):
        """Run before each test."""
        # Initialize test data
        pass
    
    def tearDown(self):
        """Run after each test."""
        # Clean up
        pass
    
    def test_something(self):
        """Test description."""
        result = function_to_test(input)
        self.assertEqual(result, expected)
```

### Assertions
Common assertions:
- `assertEqual(a, b)`: a == b
- `assertNotEqual(a, b)`: a != b
- `assertTrue(x)`: bool(x) is True
- `assertFalse(x)`: bool(x) is False
- `assertIsNone(x)`: x is None
- `assertIsNotNone(x)`: x is not None
- `assertIn(a, b)`: a in b
- `assertNotIn(a, b)`: a not in b
- `assertGreater(a, b)`: a > b
- `assertLess(a, b)`: a < b
- `assertRaises(Exception)`: code raises Exception

### Best Practices

1. **One assertion per test** (when possible)
2. **Descriptive test names**: `test_user_cannot_vote_own_message`
3. **Test edge cases**: empty strings, None, max values
4. **Use setUp/tearDown**: for common initialization
5. **Mock external dependencies**: database, API calls
6. **Keep tests fast**: avoid sleep(), network calls
7. **Test both success and failure**: happy path and errors

## Continuous Integration

To run tests automatically on commit:

### GitHub Actions
Create `.github/workflows/test.yml`:
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install -r requirements.txt
      - run: python3 tests/run_tests.py
```

### Pre-commit Hook
Create `.git/hooks/pre-commit`:
```bash
#!/bin/bash
python3 tests/run_tests.py
if [ $? -ne 0 ]; then
    echo "Tests failed. Commit aborted."
    exit 1
fi
```

## Troubleshooting

### Import Errors
If you get import errors, make sure you're running from the project root:
```bash
cd /path/to/CatLounge
python3 tests/run_tests.py
```

### Module Not Found
Ensure all dependencies are installed:
```bash
pip3 install -r requirements.txt
```

### Test Failures
1. Check the error message and traceback
2. Run the specific failing test: `python3 -m unittest tests.test_file.TestClass.test_method`
3. Add print statements for debugging
4. Check if test data is correct

## Future Tests

### Planned Test Coverage

- [ ] Integration tests for command flows
- [ ] Database transaction tests
- [ ] Telegram API mock tests
- [ ] Performance/load tests
- [ ] Security tests (injection, XSS)
- [ ] Multi-instance coordination tests

### Test Ideas

1. **Command Handler Tests**: Test each command with various inputs
2. **Permission Tests**: Verify rank-based access control
3. **Rate Limiting Tests**: Test cooldown enforcement
4. **Karma System Tests**: Test voting, levels, obfuscation
5. **Moderation Tests**: Test warn, blacklist, delete flows
6. **Message Relay Tests**: Test broadcasting, replies, reactions

## Contributing

When adding new features:
1. Write tests first (TDD)
2. Ensure all tests pass
3. Aim for >80% coverage
4. Document test purpose
5. Test edge cases

## Resources

- [Python unittest documentation](https://docs.python.org/3/library/unittest.html)
- [Testing Best Practices](https://docs.python-guide.org/writing/tests/)
- [Mock Objects](https://docs.python.org/3/library/unittest.mock.html)
