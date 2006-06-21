# (Be in -*- python -*- mode.)
#
# ====================================================================
# Copyright (c) 2000-2006 CollabNet.  All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.  The terms
# are also available at http://subversion.tigris.org/license-1.html.
# If newer versions of this license are posted there, you may use a
# newer version instead, at your option.
#
# This software consists of voluntary contributions made by many
# individuals.  For exact contribution history, see the revision
# history and logs, available at http://cvs2svn.tigris.org/.
# ====================================================================

"""This module gathers and processes statistics about CVS symbols."""

import sys

from cvs2svn_lib.boolean import *
from cvs2svn_lib.set_support import *
from cvs2svn_lib import config
from cvs2svn_lib.common import error_prefix
from cvs2svn_lib.context import Ctx
from cvs2svn_lib.log import Log
from cvs2svn_lib.artifact_manager import artifact_manager
from cvs2svn_lib.database import DB_OPEN_NEW
from cvs2svn_lib.symbol_database import BranchSymbol
from cvs2svn_lib.symbol_database import TagSymbol
from cvs2svn_lib.symbol_database import SymbolDatabase
from cvs2svn_lib.key_generator import KeyGenerator


def match_regexp_list(regexp_list, s):
  """Test whether string S matches any of the compiled regexps in
  REGEXP_LIST."""

  for regexp in regexp_list:
    if regexp.match(s):
      return True
  return False


class _Stats:
  """A summary of information about a branch.

  Members:
    id -- a unique id (integer)

    name -- the name of the symbol

    tag_create_count -- the number of files on which this symbol
        appears as a tag

    branch_create_count -- the number of files on which this symbol
        appears as a branch

    branch_commit_count -- the number of commits on this branch

    branch_blockers -- the names of any symbols that depend on the
        branch."""

  def __init__(self, id, name, tag_create_count=0,
               branch_create_count=0, branch_commit_count=0,
               branch_blockers=[]):
    self.id = id
    self.name = name
    self.tag_create_count = tag_create_count
    self.branch_create_count = branch_create_count
    self.branch_commit_count = branch_commit_count
    self.branch_blockers = set(branch_blockers)


class SymbolStatisticsCollector:
  """Collect statistics about symbols.

  Record a brief summary of information about each symbol in the RCS
  files into a database.  The database is created in CollectRevsPass
  and it is used in CollateSymbolsPass (via the SymbolStatistics
  class).

  collect_data._SymbolDataCollector inserts information into instances
  of this class by by calling its register_*() methods.

  Its main purpose is to assist in the decisions about which symbols
  can be treated as branches and tags and which may be excluded.

  The data collected by this class can be written to a text file
  (config.SYMBOL_STATISTICS_LIST)."""

  def __init__(self):
    # A hash that maps symbol names to _Stats instances
    self._stats_by_name = { }

    # A map { id -> record } for all symbols (branches and tags)
    self._stats = { }

    self._key_generator = KeyGenerator(1)

  def _get_stats(self, name):
    """Return the _Stats record for NAME, creating a new one if necessary."""

    try:
      return self._stats_by_name[name]
    except KeyError:
      stats = _Stats(self._key_generator.gen_id(), name)
      self._stats_by_name[name] = stats
      self._stats[stats.id] = stats
      return stats

  def register_tag_creation(self, name):
    """Register the creation of the tag NAME.

    Return the tag record's id."""

    stats = self._get_stats(name)
    stats.tag_create_count += 1
    return stats.id

  def register_branch_creation(self, name):
    """Register the creation of the branch NAME.

    Return the branch record's id."""

    stats = self._get_stats(name)
    stats.branch_create_count += 1
    return stats.id

  def register_branch_commit(self, name):
    """Register a commit on the branch NAME."""

    self._get_stats(name).branch_commit_count += 1

  def register_branch_blocker(self, name, blocker):
    """Register BLOCKER as a blocker on the branch NAME."""

    self._get_stats(name).branch_blockers.add(blocker)

  def write(self):
    """Store the stats database to file."""

    f = open(artifact_manager.get_temp_file(config.SYMBOL_STATISTICS_LIST),
             "w")
    for stats in self._stats.values():
      f.write(
          "%x %s %d %d %d"
          % (stats.id, stats.name, stats.tag_create_count,
             stats.branch_create_count, stats.branch_commit_count)
          )
      if stats.branch_blockers:
        f.write(' ')
        f.write(' '.join(list(stats.branch_blockers)))
      f.write('\n')
    f.close()


class SymbolStatistics:
  """Read and handle symbol statistics.

  The symbol statistics are read from a database created by
  SymbolStatisticsCollector.  This class has methods to process the
  statistics information and help with decisions about:

  1. What tags and branches should be processed/excluded

  2. What tags should be forced to be branches and vice versa (this
     class maintains some statistics to help the user decide)

  3. Are there inconsistencies?

     - A symbol that is sometimes a branch and sometimes a tag

     - A forced branch with commit(s) on it

     - A non-excluded branch depends on an excluded branch

  The data in this class is read from a text file
  (config.SYMBOL_STATISTICS_LIST)."""

  def __init__(self):
    """Read the stats database from the SYMBOL_STATISTICS_LIST file."""

    # A hash that maps symbol names to _Stats instances
    self._stats_by_name = { }

    # A map { id -> record } for all symbols (branches and tags)
    self._stats = { }

    self._key_generator = KeyGenerator(1)

    for line in open(artifact_manager.get_temp_file(
          config.SYMBOL_STATISTICS_LIST)):
      words = line.split()
      [id, name, tag_create_count,
       branch_create_count, branch_commit_count] = words[:5]
      branch_blockers = words[5:]
      id = int(id, 16)
      tag_create_count = int(tag_create_count)
      branch_create_count = int(branch_create_count)
      branch_commit_count = int(branch_commit_count)
      stats = _Stats(
          id, name, tag_create_count,
          branch_create_count, branch_commit_count, branch_blockers)
      self._stats_by_name[name] = stats
      self._stats[stats.id] = stats

  def find_excluded_symbols(self, regexp_list):
    """Return a set of all symbols that match the regexps in REGEXP_LIST."""

    excludes = set()
    for stats in self._stats.values():
      if match_regexp_list(regexp_list, stats.name):
        excludes.add(stats.name)
    return excludes

  def _find_branch_exclude_blockers(self, symbol, excludes):
    """Return the set of all blockers of SYMBOL, excluding the ones in
    the set EXCLUDES."""

    branch_blockers = set()
    if symbol in excludes:
      for blocker in self._stats_by_name[symbol].branch_blockers:
        if blocker not in excludes:
          branch_blockers.add(blocker)
    return branch_blockers

  def _find_blocked_excludes(self, excludes):
    """Find all branches not in EXCLUDES that have blocking symbols
    that are not themselves excluded.  Return a hash that maps branch
    names to a set of branch_blockers."""

    blocked_branches = { }
    for symbol in self._stats_by_name:
      branch_blockers = self._find_branch_exclude_blockers(symbol, excludes)
      if branch_blockers:
        blocked_branches[symbol] = branch_blockers
    return blocked_branches

  def _find_mismatches(self, excludes):
    """Find all symbols that are defined as both tags and branches,
    excluding the ones in EXCLUDES.  Returns a set of _Stats objects,
    one for each mismatch."""

    mismatches = set()
    for stats in self._stats.values():
      if (stats.name not in excludes
          and stats.tag_create_count > 0
          and stats.branch_create_count > 0):
        mismatches.add(stats)
    return mismatches

  def _check_blocked_excludes(self, excludes):
    """Check whether any excluded branches are blocked.

    A branch can be blocked because it has another, non-excluded
    symbol that depends on it.  If any blocked excludes are found,
    output error messages describing the situation.  Return True if
    any errors were found."""

    Log().quiet("Checking for blocked exclusions...")

    blocked_excludes = self._find_blocked_excludes(excludes)
    if not blocked_excludes:
      return False

    for branch, branch_blockers in blocked_excludes.items():
      sys.stderr.write(error_prefix + ": The branch '%s' cannot be "
                       "excluded because the following symbols depend "
                       "on it:\n" % (branch))
      for blocker in branch_blockers:
        sys.stderr.write("    '%s'\n" % (blocker))
    sys.stderr.write("\n")
    return True

  def _branch_has_commit(self, name):
    """Return True iff NAME has commits.  Returns False if NAME was
    never seen as a branch or if it has no commits."""

    stats = self._stats_by_name.get(name)
    return (stats
            and stats.branch_create_count > 0
            and stats.branch_commit_count > 0)

  def _check_invalid_forced_tags(self, excludes):
    """Check for commits on any branches that were forced to be tags.

    In that case, they can't be converted into tags.  If any invalid
    forced tags are found, output error messages describing the
    problems.  Return True iff any errors are found."""

    Log().quiet("Checking for forced tags with commits...")

    invalid_forced_tags = [ ]
    for forced_tag in Ctx().forced_tags:
      if forced_tag in excludes:
        continue
      if self._branch_has_commit(forced_tag):
        invalid_forced_tags.append(forced_tag)

    if not invalid_forced_tags:
      # No problems found:
      return False

    sys.stderr.write(error_prefix + ": The following branches cannot be "
                     "forced to be tags because they have commits:\n")
    for tag in invalid_forced_tags:
      sys.stderr.write("    '%s'\n" % (tag))
    sys.stderr.write("\n")

    return True

  def _check_symbol_mismatches(self, excludes):
    """Check for symbols that are defined as both tags and branches.

    Exclude the symbols in EXCLUDES.  If any are found, output error
    messages describing the problems.  Return True iff any problems
    are found."""

    Log().quiet("Checking for tag/branch mismatches...")

    mismatches = self._find_mismatches(excludes)

    def is_not_forced(mismatch):
      name = mismatch.name
      return not (name in Ctx().forced_tags or name in Ctx().forced_branches)

    mismatches = filter(is_not_forced, mismatches)
    if not mismatches:
      # No problems found:
      return False

    sys.stderr.write(
        error_prefix + ": The following symbols are tags in some files and "
        "branches in others.\n"
        "Use --force-tag, --force-branch and/or --exclude to resolve the "
        "symbols.\n")
    for stats in mismatches:
      sys.stderr.write(
          "    '%s' is a tag in %d files, a branch in "
          "%d files and has commits in %d files.\n"
          % (stats.name, stats.tag_create_count,
             stats.branch_create_count, stats.branch_commit_count))

    return True

  def check_consistency(self, excludes):
    """Check the non-excluded symbols for consistency.  Return True
    iff any problems were detected."""

    # It is important that we not short-circuit here:
    return (
      self._check_blocked_excludes(excludes)
      | self._check_invalid_forced_tags(excludes)
      | self._check_symbol_mismatches(excludes)
      )

  def create_symbol_database(self, excludes):
    """Create the tags database.

    Record each known symbol, except those in EXCLUDES."""

    symbol_db = SymbolDatabase(DB_OPEN_NEW)
    for stats in self._stats.values():
      if stats.name in excludes:
        # Don't write it to the database at all.
        pass
      elif stats.name in Ctx().forced_branches:
        symbol_db.add(BranchSymbol(stats.id, stats.name))
      elif stats.name in Ctx().forced_tags:
        symbol_db.add(TagSymbol(stats.id, stats.name))
      elif stats.branch_create_count > 0:
        symbol_db.add(BranchSymbol(stats.id, stats.name))
      else:
        symbol_db.add(TagSymbol(stats.id, stats.name))

