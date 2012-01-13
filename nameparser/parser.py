# -*- coding: utf-8 -*-
import logging
from constants import *

# logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('HumanName')

ENCODING = 'utf-8'

def lc(value):
    '''Lower case and remove any periods to normalize for comparison.'''
    if not value:
        return u''
    return value.lower().replace('.','')

def is_not_initial(value):
    return not re_initial.match(value)

class HumanName(object):
    
    """
    Parse a person's name into individual components.
    
    Usage::
    
        >>> from nameparser import HumanName
        >>> name = HumanName("Dr. Juan Q. Xavier de la Vega III")
        >>> name.title
        u'Dr.'
        >>> name.first
        u'Juan'
        >>> name.middle
        u'Q. Xavier'
        >>> name.last
        u'de la Vega'
        >>> name.suffix
        u'III'
        >>> name = HumanName("Doe-Ray, Col. John A. Jérôme III")
        >>> name.title
        u'Col.'
        >>> name.first
        u'John'
        >>> name.middle
        u'A. Jérôme'
        >>> name.last
        u'Doe-Ray'
        >>> name.suffix
        u'III'
        >>> name = HumanName("Juan Q. Xavier Velasquez y Garcia, Jr.")
        >>> name.title
        u''
        >>> name.first
        u'Juan'
        >>> name.middle
        u'Q. Xavier'
        >>> name.last
        u'Velasquez y Garcia'
        >>> name.suffix
        u'Jr.'
        >>> name = HumanName("Dr. Juan Q. Xavier de la Vega III")
        >>> name2 = HumanName("de la vega, dr. juan Q. xavier III")
        >>> name == name2
        True
        >>> len(name)
        5
        >>> list(name)
        ['Dr.', 'Juan', 'Q. Xavier', 'de la Vega', 'III']
        >>> name[1:-1]
        [u'Juan', u'Q. Xavier', u'de la Vega']
    
    """
    
    def __init__(self, full_name=u"", titles=TITLES, prefices=PREFICES, 
        suffices=SUFFICES, punc_titles=PUNC_TITLES, conjunctions=CONJUNCTIONS,
        capitalization_exceptions=dict(CAPITALIZATION_EXCEPTIONS)):
        
        super(HumanName, self).__init__()
        self.titles = titles
        self.punc_titles = punc_titles
        self.conjunctions = conjunctions
        self.prefices = prefices
        self.suffices = suffices
        self.capitalization_exceptions = capitalization_exceptions
        self.full_name = full_name
        self.title = u""
        self.first = u""
        self.suffixes = []
        self.middle_names = []
        self.last_names = []
        self.unparsable = False
        self.count = 0
        self.members = ['title','first','middle','last','suffix']
        if self.full_name:
            self.parse_full_name()
    
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
        lower case unicode representations are the same
        """
        return unicode(self).lower() == unicode(other).lower()
    
    def __ne__(self, other):
        return not unicode(self).lower() == unicode(other).lower()
    
    def __getitem__(self, key):
        if isinstance(key, slice):
            return [getattr(self, x) for x in self.members[key]]
        else:
            return getattr(self, self.members[key])
    
    def next(self):
        if self.count >= len(self.members):
            self.count = 0
            raise StopIteration
        else:
            c = self.count
            self.count = c + 1
            return getattr(self, self.members[c]) or self.next()

    def __unicode__(self):
        return u" ".join(self)
    
    def __str__(self):
        return self.__unicode__().encode('utf-8')
    
    def __repr__(self):
        if self.unparsable:
            return u"<%(class)s : [ Unparsable ] >" % {'class': self.__class__.__name__,}
        return u"<%(class)s : [\n\tTitle: '%(title)s' \n\tFirst: '%(first)s' \n\tMiddle: '%(middle)s' \n\tLast: '%(last)s' \n\tSuffix: '%(suffix)s'\n]>" % {
            'class': self.__class__.__name__,
            'title': self.title,
            'first': self.first,
            'middle': self.middle,
            'last': self.last,
            'suffix': self.suffix,
        }
    
    @property
    def middle(self):
        return u" ".join(self.middle_names)
    
    @property
    def last(self):
        return u" ".join(self.last_names)
    
    @property
    def suffix(self):
        return u", ".join(self.suffixes)
    
    def is_conjunction(self, piece):
        return lc(piece) in self.conjunctions and is_not_initial(piece)
    
    def is_prefix(self, piece):
        return lc(piece) in self.prefices and is_not_initial(piece)
    
    def parse_full_name(self):
        if not self.full_name:
            raise AttributeError("Missing full_name")
        
        if not isinstance(self.full_name, unicode):
            self.full_name = unicode(self.full_name, ENCODING)
        # collapse multiple spaces
        self.full_name = re.sub(re_spaces, u" ", self.full_name.strip() )
        
        # reset values
        self.title = u""
        self.first = u""
        self.suffixes = []
        self.middle_names = []
        self.last_names = []
        self.unparsable = False
        
        # break up full_name by commas
        parts = [x.strip() for x in self.full_name.split(",")]
        
        log.debug(u"full_name: " + self.full_name)
        log.debug(u"parts: " + unicode(parts))
        
        pieces = []
        if len(parts) == 1:
            
            # no commas, title first middle middle middle last suffix
            
            for part in parts:
                names = part.split(' ')
                for name in names:
                    name.replace(',','').strip()
                    pieces.append(name)
            
            log.debug(u"pieces: " + unicode(pieces))
            
            for i, piece in enumerate(pieces):
                try:
                    next = pieces[i + 1]
                except IndexError:
                    next = None

                try:
                    prev = pieces[i - 1]
                except IndexError:
                    prev = None
                
                if lc(piece) in self.titles:
                    self.title = piece
                    continue
                if piece.lower() in self.punc_titles:
                    self.title = piece
                    continue
                if not self.first:
                    self.first = piece.replace(".","")
                    continue
                if (i == len(pieces) - 2) and (lc(next) in self.suffices):
                    self.last_names.append(piece)
                    self.suffixes.append(next)
                    break
                if self.is_prefix(piece):
                    self.last_names.append(piece)
                    continue
                if self.is_conjunction(piece) and i < len(pieces) / 2:
                    self.first += ' ' + piece
                    continue
                if self.is_conjunction(prev) and (i-1) < len(pieces) / 2:
                    self.first += ' ' + piece
                    continue
                if self.is_conjunction(piece) or self.is_conjunction(next):
                    self.last_names.append(piece)
                    continue
                if i == len(pieces) - 1:
                    self.last_names.append(piece)
                    continue
                self.middle_names.append(piece)
        else:
            if lc(parts[1]) in self.suffices:
                
                # title first middle last, suffix [, suffix]
                
                names = parts[0].split(' ')
                for name in names:
                    name.replace(',','').strip()
                    pieces.append(name)
                
                log.debug(u"pieces: " + unicode(pieces))
                
                self.suffixes += parts[1:]
                
                for i, piece in enumerate(pieces):
                    try:
                        next = pieces[i + 1]
                    except IndexError:
                        next = None

                    if lc(piece) in self.titles:
                        self.title = piece
                        continue
                    if piece.lower() in self.punc_titles:
                        self.title = piece
                        continue
                    if not self.first:
                        self.first = piece.replace(".","")
                        continue
                    if i == (len(pieces) -1) and self.is_prefix(piece):
                        self.last_names.append(piece + " " + next)
                        break
                    if self.is_prefix(piece):
                        self.last_names.append(piece)
                        continue
                    if self.is_conjunction(piece) or self.is_conjunction(next):
                        self.last_names.append(piece)
                        continue
                    if i == len(pieces) - 1:
                        self.last_names.append(piece)
                        continue
                    self.middle_names.append(piece)
            else:
                
                # last, title first middles[,] suffix [,suffix]
                
                names = parts[1].split(' ')
                for name in names:
                    name.replace(',','').strip()
                    pieces.append(name)
                
                log.debug(u"pieces: " + unicode(pieces))
                
                self.last_names.append(parts[0])
                for i, piece in enumerate(pieces):
                    try:
                        next = pieces[i + 1]
                    except IndexError:
                        next = None
                    
                    if lc(piece) in self.titles:
                        self.title = piece
                        continue
                    if piece.lower() in self.punc_titles:
                        self.title = piece
                        continue
                    if not self.first:
                        self.first = piece.replace(".","")
                        continue
                    if lc(piece) in self.suffices:
                        self.suffixes.append(piece)
                        continue
                    self.middle_names.append(piece)
                try:
                    if parts[2]:
                        self.suffixes += parts[2:]
                except IndexError:
                    pass
                
        if not self.first and len(self.middle_names) < 1 and len(self.last_names) < 1:
            self.unparsable = True
            log.error(u"Unparsable full_name: " + self.full_name)
    
    def cap_word(self, word):
        if self.is_prefix(word) or self.is_conjunction(word):
            return lc(word)
        if word in self.capitalization_exceptions:
            return self.capitalization_exceptions[word]
        mac_match = re_mac.match(word)
        if mac_match:
            def cap_after_mac(m):
                return m.group(1).capitalize() + m.group(2).capitalize()
            return re_mac.sub(cap_after_mac, word)
        else:
            return word.capitalize()

    def cap_piece(self, piece):
        if not piece:
            return ""
        replacement = lambda m: self.cap_word(m.group(0))
        return re.sub(re_word, replacement, piece)

    def capitalize(self):
        """
        Capitalization Support
        ----------------------

        The HumanName class can try to guess the correct capitalization 
        of name entered in all upper or lower case. It will not adjust 
        the case of names entered in mixed case.
        
        Usage::
        
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
        name = unicode(self)
        if not (name == name.upper() or name == name.lower()):
            return
        self.title = self.cap_piece(self.title)
        self.first = self.cap_piece(self.first)
        self.middle_names = self.cap_piece(self.middle).split(' ')
        self.last_names = self.cap_piece(self.last).split(' ')
        self.suffixes = self.cap_piece(self.suffix).split(' ')
