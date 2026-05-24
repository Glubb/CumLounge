import logging
import itertools
from datetime import datetime, timedelta
from threading import RLock

from src.globals import *

class CachedMessage():
	__slots__ = ('user_id', 'time', 'warned', 'upvoted', 'downvoted')
	def __init__(self, user_id=None):
		self.user_id = user_id # who has sent this message
		self.time = datetime.now() # when was this message seen?
		self.warned = False # was the user warned for this message?
		self.upvoted = set() # set of users that have given this message karma
		self.downvoted = set() # set of users that have taken this message karma
	def isExpired(self):
		return datetime.now() >= self.time + timedelta(hours=48)
	def hasUpvoted(self, user):
		return user.id in self.upvoted
	def hasDownvoted(self, user):
		return user.id in self.downvoted
	def addUpvote(self, user):
		self.upvoted.add(user.id)
	def addDownvote(self, user):
		self.downvoted.add(user.id)

class Cache():
	def __init__(self):
		self.lock = RLock()
		self.counter = itertools.count()
		self.msgs = {} # dict(msid -> CachedMessage)
		self.idmap = {} # dict(uid -> dict(msid -> opaque))
		# reverse map for quick lookup: (uid, data) -> msid
		self.revmap = {}
		# reverse index: msid -> set(uid) to speed up deletions
		self.msid_index = {}

	def _saveMapping(self, x, uid, msid, data):
		if uid not in x:
			x[uid] = {}
		x[uid][msid] = data
		# if we're saving into the primary idmap, update reverse maps
		if x is self.idmap:
			self.revmap[(uid, data)] = msid
			if msid not in self.msid_index:
				self.msid_index[msid] = set()
			self.msid_index[msid].add(uid)

	def _lookupMapping(self, x, uid, msid, data):
		if uid not in x:
			return None
		if msid is not None:
			return x[uid].get(msid, None)
		# data is not None
		gen = ( msid for msid, _data in x[uid].items() if _data == data )
		return next(gen, None)

	def assignMessageId(self, cm: CachedMessage) -> int:
		with self.lock:
			ret = next(self.counter)
			self.msgs[ret] = cm
		return ret

	def getMessage(self, msid):
		with self.lock:
			return self.msgs.get(msid, None)

	def iterateMessages(self, functor):
		with self.lock:
			for msid, cm in list(self.msgs.items()):
				functor(msid, cm)

	def getMessages(self, uid):
		"""Get all (msid, CachedMessage) pairs for a specific user."""
		with self.lock:
			return [(msid, cm) for msid, cm in self.msgs.items() if cm.user_id == uid]

	def saveMapping(self, uid, msid, data):
		with self.lock:
			self._saveMapping(self.idmap, uid, msid, data)

	def lookupMapping(self, uid, msid=None, data=None):
		if msid is None and data is None:
			raise ValueError()
		with self.lock:
			return self._lookupMapping(self.idmap, uid, msid, data)

	def lookupMappingByData(self, data, uid=None):
		"""Find the msid for a telegram message id (data).

		If uid (chat id) is provided, perform an O(1) lookup in the reverse
		map. Otherwise fall back to scanning idmap (legacy behaviour).
		"""
		if data is None:
			raise ValueError()
		if uid is not None:
			with self.lock:
				return self.revmap.get((uid, data))
		# fallback: linear scan
		with self.lock:
			for _uid, mappings in self.idmap.items():
				for msid, _data in mappings.items():
					if _data == data:
						return msid
		return None

	def deleteMappings(self, msid):
		with self.lock:
			# fast-path: use reverse index to remove only affected uids
			uids = self.msid_index.pop(msid, None)
			if uids is None:
				# fallback: no index entry, scan all maps and revmap
				for d in self.idmap.values():
					d.pop(msid, None)
				# remove any revmap entries that pointed to this msid
				keys_to_delete = [k for k, v in self.revmap.items() if v == msid]
				for k in keys_to_delete:
					del self.revmap[k]
				return
			for uid in uids:
				d = self.idmap.get(uid)
				if d is not None:
					d.pop(msid, None)
				# also remove revmap entries for these uid/data pairs
				keys_to_delete = [k for k, v in self.revmap.items() if v == msid and k[0] == uid]
				for k in keys_to_delete:
					del self.revmap[k]

	def expire(self):
		ids = set()
		with self.lock:
			for msid in list(self.msgs.keys()):
				if not self.msgs[msid].isExpired():
					continue
				ids.add(msid)
				# delete message itself and from mappings
				del self.msgs[msid]
				self.deleteMappings(msid)
		if len(ids) > 0:
			logging.debug("Expired %d entries from cache", len(ids))
		return ids
