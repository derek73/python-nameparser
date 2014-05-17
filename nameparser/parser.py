# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging
from nameparser.util import u
from nameparser.util import text_type
from nameparser.util import lc
from nameparser.config import CONSTANTS
from nameparser.config import Constants

# http://code.google.com/p/python-nameparser/issues/detail?id=10
log = logging.getLogger('HumanName')
try:
    log.addHandler(logging.NullHandler())
except AttributeError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass
    log.addHandler(NullHandler())
log.setLevel(logging.ERROR)

ENCODING = 'utf-8'


class HumanName(object):
    """
    Parse a person's name into individual components.
    
    **HumanName Instance Attributes**
    
    * o.title
    * o.first
    * o.middle
    * o.last
    * o.suffix
    * o.nickname
    
    Instantiation assigns to ``full_name``, and assignment to :py:attr:`full_name`
    triggers :py:func:`parse_full_name`, where most of the action happens.
     
    :param str full_name: The name string to be parsed.
    :param constants constants: 
        a :py:class:`~nameparser.config.Constants` instance. Pass ``None`` for 
        `per-instance config <customize.html>`_. 
    :param str encoding: string representing the encoding of your input
    :param str string_format: python string formatting 
    """
    
    CONSTANTS = CONSTANTS
    
    def __init__(self, full_name="", constants=CONSTANTS, encoding=ENCODING, 
                string_format=None):
        
        self.C = constants
        """
        A reference to the configuration for this instance, which may be a
        reference to the module-wide instance at :py:mod:`~nameparser.config.CONSTANTS`.
        See `Customizing the Parser <customize.html>`_.
        """
        
        self.has_own_config = False
        
        if not self.C:
            self.C = Constants()
        if self.C is not self.CONSTANTS:
            #: True if this instance is not using the module-level configuration.
            self.has_own_config = True
        
        self.ENCODING = encoding
        self.string_format = string_format
        self.count = 0
        self._members = ['title','first','middle','last','suffix']
        self.unparsable = True
        self._full_name = ''
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
            return getattr(self, self._members[key])

    def next(self):
        return self.__next__()

    def __next__(self):
        if self.count >= len(self._members):
            self.count = 0
            raise StopIteration
        else:
            c = self.count
            self.count = c + 1
            return getattr(self, self._members[c]) or next(self)

    def __unicode__(self):
        if self.string_format:
            # string_format = "{title} {first} {middle} {last} {suffix}"
            return self.string_format.format(**self._dict)
        return " ".join(self)
    
    def __str__(self):
        return self.__unicode__()
    
    def __repr__(self):
        if self.unparsable:
            return "<%(class)s : [ Unparsable ] >" % {'class': self.__class__.__name__,}
        return "<%(class)s : [\n\ttitle: '%(title)s' \n\tfirst: '%(first)s' \n\tmiddle: '%(middle)s' \n\tlast: '%(last)s' \n\tsuffix: '%(suffix)s'\n\tnickname: '%(nickname)s'\n]>" % {
            'class': self.__class__.__name__,
            'title': self.title,
            'first': self.first,
            'middle': self.middle,
            'last': self.last,
            'suffix': self.suffix,
            'nickname': self.nickname,
        }
    
    @property
    def _dict(self):
        d = {}
        for m in self._members:
            d[m] = getattr(self, m)
        return d
    
    ### attributes
    
    @property
    def title(self):
        return " ".join(self.title_list)
    
    @property
    def first(self):
        return " ".join(self.first_list)
    
    @property
    def middle(self):
        return " ".join(self.middle_list)
    
    @property
    def last(self):
        return " ".join(self.last_list)
    
    @property
    def suffix(self):
        return ", ".join(self.suffix_list)
    
    @property
    def nickname(self):
        return " ".join(self.nickname_list)
    
    ### setter methods
    
    def _set_list(self, attr, value):
        setattr(self, attr+"_list", self.parse_pieces([value]))
    
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
        """Is in the titles set"""
        return lc(value) in self.C.titles
    
    def is_conjunction(self, piece):
        """Is in the conjuctions set or :py:func:`is_an_initial()`"""
        return lc(piece) in self.C.conjunctions and not self.is_an_initial(piece)
    
    def is_prefix(self, piece):
        """Is in the prefixes set or :py:func:`is_an_initial()`"""
        return lc(piece) in self.C.prefixes and not self.is_an_initial(piece)
    
    def is_suffix(self, piece):
        """Is in the suffixes set or :py:func:`is_an_initial()`"""
        return lc(piece) in self.C.suffixes and not self.is_an_initial(piece)
    
    def is_rootname(self, piece):
        '''Is not a known title, suffix or prefix. Just first, middle, last names.'''
        return lc(piece) not in self.C.suffixes_prefixes_titles \
            and not self.is_an_initial(piece) 
    
    def is_an_initial(self, value):
        """Matches the regular expression for initials."""
        return self.C.regexes.initial.match(value) or False

    # def is_a_roman_numeral(value):
    #     return re_roman_numeral.match(value) or False

    
    ### full_name parser
    
    @property
    def full_name(self):
        return self._full_name
    
    @full_name.setter
    def full_name(self, value):
        self._full_name = value
        self.parse_full_name()

    
    def pre_process(self):
        """
        This method happens at the beginning of the :py:func:`parse_full_name` before
        any other processing of the string aside from unicode normalization, so
        it's a good place to do any custom handling in a subclass.
        """
        self.parse_nicknames()
        

    def post_process(self):
        """
        This happens at the end of the :py:func:`parse_full_name` after
        all other processing has taken place.
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

        Basic flow is the hand off to :py:func:`pre_process` to handle nicknames, split
        on commas to figure out which comma format to work with. :py:func:`parse_pieces`
        splits on spaces and :py:func:`join_on_conjunctions` joins any pieces next to
        conjunctions.
        """
        
        self.title_list = []
        self.first_list = []
        self.middle_list = []
        self.last_list = []
        self.suffix_list = []
        self.nickname_list = []
        self.unparsable = True
        
        if not isinstance(self._full_name, text_type):
            self._full_name = u(self._full_name, self.ENCODING)
        
        self.pre_process()
        
        # collapse multiple spaces
        self._full_name = self.C.regexes.spaces.sub(" ", self._full_name.strip())
        
        # break up full_name by commas
        parts = [x.strip() for x in self._full_name.split(",")]
        
        log.debug("full_name: {0}".format(self._full_name))
        log.debug("parts: {0}".format(parts))
        
        if len(parts) == 1:
            
            # no commas, title first middle middle middle last suffix
            
            pieces = self.parse_pieces(parts)
            
            for i, piece in enumerate(pieces):
                try:
                    nxt = pieces[i + 1]
                except IndexError:
                    nxt = None
                
                # title must have a next piece, unless it's just a title
                if self.is_title(piece) and (nxt or len(pieces) == 1):
                    self.title_list.append(piece)
                    continue
                if not self.first:
                    self.first_list.append(piece)
                    continue
                if (i == len(pieces) - 2) and self.is_suffix(nxt):
                    self.last_list.append(piece)
                    self.suffix_list.append(nxt)
                    break
                if not nxt:
                    self.last_list.append(piece)
                    continue
                
                self.middle_list.append(piece)
        else:
            if self.is_suffix(parts[1]):
                
                # suffix comma: title first middle last, suffix [, suffix]
                
                self.suffix_list += parts[1:]
                
                pieces = self.parse_pieces(parts[0].split(' '))
                log.debug("pieces: {0}".format(u(pieces)))
                
                for i, piece in enumerate(pieces):
                    try:
                        nxt = pieces[i + 1]
                    except IndexError:
                        nxt = None

                    if self.is_title(piece) and (nxt or len(pieces) == 1):
                        self.title_list.append(piece)
                        continue
                    if not self.first:
                        self.first_list.append(piece)
                        continue
                    if not nxt:
                        self.last_list.append(piece)
                        continue
                    self.middle_list.append(piece)
            else:
                
                # lastname comma: last, title first middles[,] suffix [,suffix]
                pieces = self.parse_pieces(parts[1].split(' '), 1)
                
                log.debug("pieces: {0}".format(u(pieces)))
                
                self.last_list.append(parts[0])
                for i, piece in enumerate(pieces):
                    try:
                        nxt = pieces[i + 1]
                    except IndexError:
                        nxt = None
                    
                    if self.is_title(piece) and (nxt or len(pieces) == 1):
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
            log.info("Unparsable full_name: " + self._full_name)
        else:
            self.unparsable = False
            self.post_process()

    def parse_pieces(self, parts, additional_parts_count=0):
        """
        Split parts on spaces and remove commas, join on conjunctions and
        lastname prefixes.
        
        :param int additional_parts_count: 
        
            if the comma format contains other parts, we need to know 
            how many there are to decide if things should be considered a conjunction.
        :return: pieces split on spaces and joined on conjunctions
        :rtype: list
        """
        
        ps = []
        for part in parts:
            ps += [x.strip(' ,') for x in part.split(' ')]
        
        # if there is a period that is not at the end of a piece, split it on periods
        pieces = []
        for piece in ps:
            if piece[:-1].find('.') >= 0:
                p = [_f for _f in piece.split('.') if _f]
                pieces += [x+'.' for x in p]
            else:
                pieces += [piece]
        
        
        return self.join_on_conjunctions(pieces, additional_parts_count)
        
    def join_on_conjunctions(self, pieces, additional_parts_count=0):
        """
        Join conjunctions to surrounding pieces, e.g.:
        ['Mr. and Mrs.'], ['King of the Hill'], ['Jack and Jill'], ['Velasquez y Garcia']
        
        :return: new list with piece next to conjunctions merged into one piece with spaces in it.
        :rtype: list
        
        """
        
        for conj in filter(self.is_conjunction, pieces[::-1]): # reverse sorted list
            
            # loop through the pieces backwards, starting at the end of the list.
            # Join conjunctions to the pieces on either side of them.
            
            if len(conj) == 1 and \
                len(list(filter(self.is_rootname, pieces))) + additional_parts_count < 4:
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
        try:
            for prefix in prefixes:
                try:
                    i = pieces.index(prefix)
                except ValueError:
                    # if two prefixes in a row ("de la Vega"), have to do 
                    # extra work to find the index the second time around
                    def find_p(p):
                        return p.endswith(prefix) # closure on prefix
                    m = list(filter(find_p, pieces))
                    # I wonder if some input will throw an IndexError here. 
                    # Means it can't find prefix anyore.
                    i = pieces.index(m[0])
                pieces[i] = ' '.join(pieces[i:i+2])
                pieces.pop(i+1)
        except IndexError:
            pass
            
        log.debug("pieces: {0}".format(pieces))
        return pieces
    
    
    ### Capitalization Support
    
    def cap_word(self, word):
        if self.is_prefix(word) or self.is_conjunction(word):
            return lc(word)
        exceptions = self.C.capitalization_exceptions
        if word in exceptions:
            return exceptions[word]
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
        
        ::
        
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
        self.title_list = self.cap_piece(self.title).split(' ')
        self.first_list = self.cap_piece(self.first).split(' ')
        self.middle_list = self.cap_piece(self.middle).split(' ')
        self.last_list = self.cap_piece(self.last).split(' ')
        self.suffix_list = self.cap_piece(self.suffix).split(' ')
