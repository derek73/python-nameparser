# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import sys
from nameparser.util import u
from nameparser.util import text_types, binary_type
from nameparser.util import lc
from nameparser.util import log
from nameparser.config import CONSTANTS
from nameparser.config import Constants


ENCODING = 'utf-8'


class HumanName(object):
    """
    Parse a person's name into individual components.
    
    Instantiation assigns to ``full_name``, and assignment to :py:attr:`full_name`
    triggers :py:func:`parse_full_name`. After parsing the name, these instance 
    attributes are available.
    
    **HumanName Instance Attributes**
    
    * :py:attr:`title`
    * :py:attr:`first`
    * :py:attr:`middle`
    * :py:attr:`last`
    * :py:attr:`suffix`
    * :py:attr:`nickname`
    
    :param str full_name: The name string to be parsed.
    :param constants constants: 
        a :py:class:`~nameparser.config.Constants` instance. Pass ``None`` for 
        `per-instance config <customize.html>`_. 
    :param str encoding: string representing the encoding of your input
    :param str string_format: python string formatting 
    """
    
    has_own_config = False
    """True if this instance is not using the shared module-level configuration. Read only."""
    
    C = CONSTANTS
    """
    A reference to the configuration for this instance, which may or may not be a
    reference to the shared, module-wide instance at :py:mod:`~nameparser.config.CONSTANTS`.
    See `Customizing the Parser <customize.html>`_.
    """
    
    original = ''
    """
    The original string, untouched by the parser.
    """
    
    _count = 0
    _members = ['title','first','middle','last','suffix','nickname']
    unparsable = True
    _full_name = ''
    
    def __init__(self, full_name="", constants=CONSTANTS, encoding=ENCODING, 
                string_format=None):
        global CONSTANTS
        self.C = constants
        if not self.C:
            self.C = Constants()
        if self.C is not CONSTANTS:
            self.has_own_config = True
        
        self.ENCODING = encoding
        self.string_format = string_format
        self.full_name = full_name
    
    def __iter__(self):
        return self
    
    def __len__(self):
        l = 0
        for x in self:
            l += 1
        return l
    
    def __eq__(self, other):
        """
        HumanName instances are equal to other objects whose 
        lower case unicode representation is the same.
        """
        return (u(self)).lower() == (u(other)).lower()
    
    def __ne__(self, other):
        return not (u(self)).lower() == (u(other)).lower()
    
    def __getitem__(self, key):
        if isinstance(key, slice):
            return [getattr(self, x) for x in self._members[key]]
        else:
            return getattr(self, key)

    def __setitem__(self, key, value):
        if key in self._members:
            self._set_list(key, value)
        else:
            raise KeyError("Not a valid HumanName attribute", key)

    def next(self):
        return self.__next__()

    def __next__(self):
        if self._count >= len(self._members):
            self._count = 0
            raise StopIteration
        else:
            c = self._count
            self._count = c + 1
            return getattr(self, self._members[c]) or next(self)

    def __unicode__(self):
        if self.string_format:
            # string_format = "{title} {first} {middle} {last} {suffix} ({nickname})"
            return self.collapse_whitespace(self.string_format.format(**self.as_dict())).strip(', ')
        return " ".join(self)
    
    def __str__(self):
        if sys.version >= '3':
            return self.__unicode__()
        return self.__unicode__().encode(self.ENCODING)
    
    def __repr__(self):
        if self.unparsable:
            _string = "<%(class)s : [ Unparsable ] >" % {'class': self.__class__.__name__,}
        else:
            _string = "<%(class)s : [\n\ttitle: '%(title)s' \n\tfirst: '%(first)s' \n\tmiddle: '%(middle)s' \n\tlast: '%(last)s' \n\tsuffix: '%(suffix)s'\n\tnickname: '%(nickname)s'\n]>" % {
                'class': self.__class__.__name__,
                'title': self.title,
                'first': self.first,
                'middle': self.middle,
                'last': self.last,
                'suffix': self.suffix,
                'nickname': self.nickname,
            }
        if sys.version >= '3':
            return _string
        return _string.encode(self.ENCODING)
    
    def as_dict(self, include_empty=True):
        """
        Return the parsed name as a dictionary of its attributes.
        
        :param bool include_empty: Include keys in the dictionary for empty name attributes.
        :rtype: dict
        
        .. doctest::
        
            >>> name = HumanName("Bob Dole")
            >>> name.as_dict()
            {u'last': u'Dole', u'suffix': u'', u'title': u'', u'middle': u'', u'nickname': u'', u'first': u'Bob'}
            >>> name.as_dict(False)
            {u'last': u'Dole', u'first': u'Bob'}
            
        """
        d = {}
        for m in self._members:
            if include_empty:
                d[m] = getattr(self, m)
            else:
                val = getattr(self, m)
                if val:
                    d[m] = val
        return d
        
    ### attributes
    
    @property
    def title(self):
        """
        The person's titles. Any string of consecutive pieces in 
        :py:mod:`~nameparser.config.titles` or :py:mod:`~nameparser.config.conjunctions`
        at the beginning of :py:attr:`full_name`.
        """
        return " ".join(self.title_list)
    
    @property
    def first(self):
        """
        The person's first name. The first name piece after any known 
        :py:attr:`title` pieces parsed from :py:attr:`full_name`.
        """
        return " ".join(self.first_list)
    
    @property
    def middle(self):
        """
        The person's middle names. All name pieces after the first name and before 
        the last name parsed from :py:attr:`full_name`.
        """
        return " ".join(self.middle_list)
    
    @property
    def last(self):
        """
        The person's last name. The last name piece parsed from 
        :py:attr:`full_name`.
        """
        return " ".join(self.last_list)
    
    @property
    def suffix(self):
        """
        The persons's suffixes. Pieces at the end of the name that are found in
        :py:mod:`~nameparser.config.suffixes`, or pieces that are at the end
        of comma separated formats, e.g. "Lastname, Title Firstname Middle[,] Suffix 
        [, Suffix]" parsed from :py:attr:`full_name`.
        """
        return ", ".join(self.suffix_list)
    
    @property
    def nickname(self):
        """
        The person's nicknames. Any text found inside of quotes (``""``) or 
        parenthesis (``()``)
        """
        return " ".join(self.nickname_list)
    
    ### setter methods
    
    def _set_list(self, attr, value):
        if isinstance(value, list):
            val = value
        elif isinstance(value, text_types):
            val = [value]
        else:
            raise TypeError("Can only assign strings and lists to name attributes. "
                    "Got {0}".format(type(value)))
        setattr(self, attr+"_list", self.parse_pieces(val))
    
    @title.setter
    def title(self, value):
        self._set_list('title', value)
    
    @first.setter
    def first(self, value):
        self._set_list('first', value)
    
    @middle.setter
    def middle(self, value):
        self._set_list('middle', value)
    
    @last.setter
    def last(self, value):
        self._set_list('last', value)
    
    @suffix.setter
    def suffix(self, value):
        self._set_list('suffix', value)
    
    @nickname.setter
    def nickname(self, value):
        self._set_list('nickname', value)
    
    ### Parse helpers
    
    def is_title(self, value):
        """Is in the :py:data:`~nameparser.config.titles.TITLES` set."""
        return lc(value) in self.C.titles
    
    def is_conjunction(self, piece):
        """Is in the conjuctions set and not :py:func:`is_an_initial()`."""
        return lc(piece) in self.C.conjunctions and not self.is_an_initial(piece)
    
    def is_prefix(self, piece):
        """Is in the prefixes set and not :py:func:`is_an_initial()`."""
        return lc(piece) in self.C.prefixes and not self.is_an_initial(piece)

    def is_roman_numeral(self, value):
        """
        Matches the ``roman_numeral`` regular expression in 
        :py:data:`~nameparser.config.regexes.REGEXES`.
        """
        return bool(self.C.regexes.roman_numeral.match(value))
    
    def is_suffix(self, piece):
        """
        Is in the suffixes set and not :py:func:`is_an_initial()`. 
        
        Some suffixes may be acronyms (M.B.A) while some are not (Jr.), 
        so we remove the periods from `piece` when testing against
        `C.suffix_acronyms`.
        """
        # suffixes may have periods inside them like "M.D."
        return ((lc(piece).replace('.','') in self.C.suffix_acronyms) \
            or (lc(piece) in self.C.suffix_not_acronyms)) \
            and not self.is_an_initial(piece)
    
    def are_suffixes(self, pieces):
        """Return True if all pieces are suffixes."""
        for piece in pieces:
            if not self.is_suffix(piece):
                return False
        return True
    
    def is_rootname(self, piece):
        '''Is not a known title, suffix or prefix. Just first, middle, last names.'''
        return lc(piece) not in self.C.suffixes_prefixes_titles \
            and not self.is_an_initial(piece) 
    
    def is_an_initial(self, value):
        """
        Words with a single period at the end, or a single uppercase letter.
        
        Matches the ``initial`` regular expression in 
        :py:data:`~nameparser.config.regexes.REGEXES`.
        """
        return bool(self.C.regexes.initial.match(value))

    
    ### full_name parser
    
    @property
    def full_name(self):
        """The name string to be parsed."""
        return self._full_name
    
    @full_name.setter
    def full_name(self, value):
        self.original = value
        self._full_name = value
        if isinstance(value, binary_type):
            self._full_name = value.decode(self.ENCODING)
        self.parse_full_name()
    
    def collapse_whitespace(self, string):
        # collapse multiple spaces into single space
        return self.C.regexes.spaces.sub(" ", string.strip())
    
    def pre_process(self):
        """
        This method happens at the beginning of the :py:func:`parse_full_name` before
        any other processing of the string aside from unicode normalization, so
        it's a good place to do any custom handling in a subclass. 
        Runs :py:func:`parse_nicknames`.
        """
        self.parse_nicknames()
        

    def post_process(self):
        """
        This happens at the end of the :py:func:`parse_full_name` after
        all other processing has taken place. Runs :py:func:`handle_firstnames`.
        """
        self.handle_firstnames()

    def parse_nicknames(self):
        """
        The content of parenthesis or double quotes in the name will
        be treated as nicknames. This happens before any other
        processing of the name.
        """
        # https://code.google.com/p/python-nameparser/issues/detail?id=33
        re_nickname = self.C.regexes.nickname
        if re_nickname.search(self._full_name):
            self.nickname_list = re_nickname.findall(self._full_name)
            self._full_name = re_nickname.sub('', self._full_name)

    def handle_firstnames(self):
        """
        If there are only two parts and one is a title, assume it's a last name
        instead of a first name. e.g. Mr. Johnson. Unless it's a special title
        like "Sir", then when it's followed by a single name that name is always
        a first name. 
        """
        if self.title \
                and len(self) == 2 \
                and not lc(self.title) in self.C.first_name_titles:
            self.last, self.first = self.first, self.last

    def parse_full_name(self):
        """
        The main parse method for the parser. This method is run upon assignment to the
        :py:attr:`full_name` attribute or instantiation.

        Basic flow is to hand off to :py:func:`pre_process` to handle nicknames. It
        then splits on commas and chooses a code path depending on the number of commas.
        :py:func:`parse_pieces` then splits those parts on spaces and
        :py:func:`join_on_conjunctions` joins any pieces next to conjunctions. 
        """
        
        self.title_list = []
        self.first_list = []
        self.middle_list = []
        self.last_list = []
        self.suffix_list = []
        self.nickname_list = []
        self.unparsable = True
        
        
        self.pre_process()
        
        self._full_name = self.collapse_whitespace(self._full_name)
        
        # break up full_name by commas
        parts = [x.strip() for x in self._full_name.split(",")]
        
        log.debug("full_name: {0}".format(self._full_name))
        log.debug("parts: {0}".format(parts))
        
        if len(parts) == 1:
            
            # no commas, title first middle middle middle last suffix
            #            part[0]
            
            pieces = self.parse_pieces(parts)
            p_len = len(pieces)
            for i, piece in enumerate(pieces):
                try:
                    nxt = pieces[i + 1]
                except IndexError:
                    nxt = None
                
                # title must have a next piece, unless it's just a title
                if self.is_title(piece) and (nxt or p_len == 1) and not self.first:
                    self.title_list.append(piece)
                    continue
                if not self.first:
                    self.first_list.append(piece)
                    continue
                if self.are_suffixes(pieces[i+1:]) or \
                        ( 
                            # if the next piece is the last piece and a roman numeral 
                            # but this piece is not an initial
                            self.is_roman_numeral(nxt) and i == p_len - 2 
                            and not self.is_an_initial(piece)
                        ):
                    self.last_list.append(piece)
                    self.suffix_list += pieces[i+1:]
                    break
                if not nxt:
                    self.last_list.append(piece)
                    continue
                
                self.middle_list.append(piece)
        else:
            if self.are_suffixes(parts[1].split(' ')):
                
                # suffix comma: title first middle last [suffix], suffix [suffix] [, suffix]
                #               parts[0],                         parts[1:...]
                
                self.suffix_list += parts[1:]
                pieces = self.parse_pieces(parts[0].split(' '))
                log.debug("pieces: {0}".format(u(pieces)))
                for i, piece in enumerate(pieces):
                    try:
                        nxt = pieces[i + 1]
                    except IndexError:
                        nxt = None

                    if self.is_title(piece) and (nxt or len(pieces) == 1) and not self.first:
                        self.title_list.append(piece)
                        continue
                    if not self.first:
                        self.first_list.append(piece)
                        continue
                    if self.are_suffixes(pieces[i+1:]):
                        self.last_list.append(piece)
                        self.suffix_list = pieces[i+1:] + self.suffix_list
                        break
                    if not nxt:
                        self.last_list.append(piece)
                        continue
                    self.middle_list.append(piece)
            else:
                
                # lastname comma: last [suffix], title first middles[,] suffix [,suffix]
                #                 parts[0],      parts[1],              parts[2:...]
                pieces = self.parse_pieces(parts[1].split(' '), 1)
                
                log.debug("pieces: {0}".format(u(pieces)))
                
                # lastname part may have suffixes in it
                lastname_pieces = self.parse_pieces(parts[0].split(' '), 1)
                for piece in lastname_pieces:
                    # the first one is always a last name, even if it look like a suffix
                    if self.is_suffix(piece) and len(self.last_list) > 0:
                        self.suffix_list.append(piece)
                    else:
                        self.last_list.append(piece)
                
                for i, piece in enumerate(pieces):
                    try:
                        nxt = pieces[i + 1]
                    except IndexError:
                        nxt = None
                    
                    if self.is_title(piece) and (nxt or len(pieces) == 1) and not self.first:
                        self.title_list.append(piece)
                        continue
                    if not self.first:
                        self.first_list.append(piece)
                        continue
                    if self.is_suffix(piece):
                        self.suffix_list.append(piece)
                        continue
                    self.middle_list.append(piece)
                try:
                    if parts[2]:
                        self.suffix_list += parts[2:]
                except IndexError:
                    pass
                
        if len(self) < 0:
            log.info("Unparsable: \"{}\" ".format(self.original))
        else:
            self.unparsable = False
        self.post_process()


    def parse_pieces(self, parts, additional_parts_count=0):
        """
        Split parts on spaces and remove commas, join on conjunctions and
        lastname prefixes. If parts have periods in the middle, try splitting
        on periods and check if the parts are titles or suffixes. If they are
        add to the constant so they will be found.
        
        :param list parts: name part strings from the comma split
        :param int additional_parts_count: 
        
            if the comma format contains other parts, we need to know 
            how many there are to decide if things should be considered a conjunction.
        :return: pieces split on spaces and joined on conjunctions
        :rtype: list
        """
        
        output = []
        for part in parts:
            if not isinstance(part, text_types):
                raise TypeError("Name parts must be strings. Got {0}".format(type(part)))
            output += [x.strip(' ,') for x in part.split(' ')]
        
        # If there's periods, check if it's titles without spaces and add spaces
        # so they get picked up later as titles.
        for part in output:
            # if this part has a period not at the beginning or end
            if self.C.regexes.period_not_at_end.match(part):
                # split on periods, any of the split pieces titles or suffixes? ("Lt.Gov.")
                period_chunks = part.split(".")
                titles   = filter(self.is_title,  period_chunks)
                suffixes = filter(self.is_suffix, period_chunks)
                
                # add the part to the constant so it will be found
                if len(list(titles)):
                    self.C.titles.add(part)
                    continue
                if len(list(suffixes)):
                    self.C.suffixes.add(part)
                    continue
        
        return self.join_on_conjunctions(output, additional_parts_count)
        
    def join_on_conjunctions(self, pieces, additional_parts_count=0):
        """
        Join conjunctions to surrounding pieces, e.g.:
        ['Mr. and Mrs.'], ['King of the Hill'], ['Jack and Jill'], ['Velasquez y Garcia']
        
        :param list pieces: name pieces strings after split on spaces
        :param int additional_parts_count: 
        :return: new list with piece next to conjunctions merged into one piece with spaces in it.
        :rtype: list
        
        """
        length = len(pieces) + additional_parts_count
        # don't join on conjuctions if there's only 2 parts
        if length < 3:
            return pieces
        
        for conj in filter(self.is_conjunction, pieces[::-1]): # reverse sorted list
            
            # loop through the pieces backwards, starting at the end of the list.
            # Join conjunctions to the pieces on either side of them.
            
            rootname_pieces = [p for p in pieces if self.is_rootname(p)]
            total_length= len(rootname_pieces) + additional_parts_count
            if len(conj) == 1 and total_length < 4:
                # if there are only 3 total parts (minus known titles, suffixes and prefixes) 
                # and this conjunction is a single letter, prefer treating it as an initial
                # rather than a conjunction.
                # http://code.google.com/p/python-nameparser/issues/detail?id=11
                continue
            
            try:
                i = pieces.index((conj))
            except ValueError:
                log.error("Couldn't find '{conj}' in pieces. i={i}, pieces={pieces}".format(**locals()))
                continue
            
            if i < len(pieces) - 1: 
                # if this is not the last piece
                
                if i is 0:
                    # if this is the first piece and it's a conjunction
                    nxt = pieces[i+1]
                    const = self.C.conjunctions
                    if self.is_title(nxt):
                        const = self.C.titles
                    new_piece = ' '.join(pieces[0:2])
                    const.add(new_piece)
                    pieces[i] = new_piece
                    pieces.pop(i+1)
                    continue
                
                if self.is_conjunction(pieces[i-1]):
                    
                    # if the piece in front of this one is a conjunction too,
                    # add new_piece (this conjuction and the following piece) 
                    # to the conjuctions constant so that it is recognized
                    # as a conjunction in the next loop. 
                    # e.g. for ["Lord","of","the Universe"], put "the Universe"
                    # into the conjunctions constant.
                    
                    new_piece = ' '.join(pieces[i:i+2])
                    self.C.conjunctions.add(new_piece)
                    pieces[i] = new_piece
                    pieces.pop(i+1)
                    continue
                
                new_piece = ' '.join(pieces[i-1:i+2])
                if self.is_title(pieces[i-1]):
                    
                    # if the second name is a title, assume the first one is too and add the 
                    # two titles with the conjunction between them to the titles constant 
                    # so the combo we just created gets parsed as a title. 
                    # e.g. "Mr. and Mrs." becomes a title.
                    
                    self.C.titles.add(new_piece)
                
                pieces[i-1] = new_piece
                pieces.pop(i)
                pieces.pop(i)
        
        # join prefixes to following lastnames: ['de la Vega'], ['van Buren']
        prefixes = list(filter(self.is_prefix, pieces))
        if prefixes:
            i = pieces.index(prefixes[0])
            # join everything after the prefix until the next suffix
            next_suffix = list(filter(self.is_suffix, pieces[i:]))
            if next_suffix:
                j = pieces.index(next_suffix[0])
                new_piece = ' '.join(pieces[i:j])
                pieces = pieces[:i] + [new_piece] + pieces[j:]
            else:
                new_piece = ' '.join(pieces[i:])
                pieces = pieces[:i] + [new_piece]
            
        log.debug("pieces: {0}".format(pieces))
        return pieces
    
    
    ### Capitalization Support
    
    def cap_word(self, word):
        if self.is_prefix(word) or self.is_conjunction(word):
            return lc(word)
        exceptions = self.C.capitalization_exceptions
        if lc(word) in exceptions:
            return exceptions[lc(word)]
        mac_match = self.C.regexes.mac.match(word)
        if mac_match:
            def cap_after_mac(m):
                return m.group(1).capitalize() + m.group(2).capitalize()
            return self.C.regexes.mac.sub(cap_after_mac, word)
        else:
            return word.capitalize()

    def cap_piece(self, piece):
        if not piece:
            return ""
        replacement = lambda m: self.cap_word(m.group(0))
        return self.C.regexes.word.sub(replacement, piece)

    def capitalize(self):
        """
        The HumanName class can try to guess the correct capitalization 
        of name entered in all upper or lower case. It will not adjust 
        the case of names entered in mixed case.
        
        **Usage**
        
        .. doctest:: capitalize
        
            >>> name = HumanName('bob v. de la macdole-eisenhower phd')
            >>> name.capitalize()
            >>> unicode(name)
            u'Bob V. de la MacDole-Eisenhower Ph.D.'
            >>> # Don't touch good names
            >>> name = HumanName('Shirley Maclaine')
            >>> name.capitalize()
            >>> unicode(name) 
            u'Shirley Maclaine'
        
        """
        name = u(self)
        if not (name == name.upper() or name == name.lower()):
            return
        self.title_list  = self.cap_piece(self.title ).split(' ')
        self.first_list  = self.cap_piece(self.first ).split(' ')
        self.middle_list = self.cap_piece(self.middle).split(' ')
        self.last_list   = self.cap_piece(self.last  ).split(' ')
        self.suffix_list = self.cap_piece(self.suffix).split(', ')
