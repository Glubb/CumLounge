# Reply and Caption Fix

## Issues Fixed

### 1. Reply Functionality Not Working
**Problem**: When users replied to messages, the reply chain wasn't preserved. All messages appeared as standalone messages instead of being threaded.

**Root Cause**: 
- `relay()` function never checked if incoming message was a reply (`message.reply_to_message`)
- `send_thread()` hardcoded `reply_to = None` instead of using `item.reply_msid`
- Reply chain mapping wasn't being looked up or passed through

**Fix**:
- `relay()` now detects `message.reply_to_message` and resolves it to `reply_msid`
- Looks up the original message's msid from cache or DB using the replied message_id
- Passes `reply_msid` through to `send_to_single()`
- `send_thread()` now resolves `reply_msid` to each recipient's specific `message_id` before sending
- Uses cache first, falls back to DB for cross-process support

### 2. Image/Media Captions Not Being Sent
**Problem**: When users uploaded images with text captions, only the image was sent without the text.

**Root Cause**:
- `send_to_single_inner()` never extracted or passed captions from the original message
- Photo, video, document, animation, and audio sends didn't include `caption` parameter

**Fix**:
- Extract caption from message: `caption = force_caption if force_caption is not None else getattr(ev, 'caption', None)`
- Add caption to kwargs for all media types that support it:
  - `bot.send_photo()` with `caption=`
  - `bot.send_video()` with `caption=`
  - `bot.send_document()` with `caption=`
  - `bot.send_animation()` with `caption=`
  - `bot.send_audio()` with `caption=`

## Testing Instructions

### Test 1: Reply Chain
1. User A sends a message: "Hello"
2. User B replies to that message: "Hi there"
3. User C replies to User B's message: "How are you?"
4. **Expected**: All users see the threaded replies linked together

### Test 2: Image with Caption
1. User A uploads a photo with caption: "Check out this cool picture!"
2. **Expected**: All users see the photo with the caption text below it

### Test 3: Document with Caption
1. User A uploads a PDF with caption: "Here's the report"
2. **Expected**: All users see the document with the caption

### Test 4: Reply to Media
1. User A sends an image with caption: "What do you think?"
2. User B replies to that image: "Looks great!"
3. **Expected**: User B's reply appears threaded under the image for all users

## Technical Details

### Message Flow
```
User A sends message (reply to X)
    ↓
relay() detects reply_to_message
    ↓
Looks up msid of message X (cache → DB fallback)
    ↓
Creates new msid for A's message
    ↓
Broadcasts to all users with reply_msid=X
    ↓
send_thread() resolves X to each recipient's message_id
    ↓
Sends with reply_to_message_id parameter
```

### Caption Flow
```
User sends photo with caption
    ↓
relay() receives message with caption attribute
    ↓
send_to_single() queues message
    ↓
send_to_single_inner() extracts caption
    ↓
Adds caption to bot.send_photo() kwargs
    ↓
All recipients see image with caption
```

## Files Modified
- `src/telegram.py`:
  - `send_to_single_inner()`: Added caption extraction and passing
  - `send_thread()`: Added reply_msid resolution to reply_to message_id
  - `relay()`: Added reply detection and msid lookup

## No Database Changes
- Uses existing message_mapping table
- Uses existing cache lookup methods
- Fully compatible with multi-instance setup
