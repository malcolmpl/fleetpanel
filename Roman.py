#!/usr/bin/python
# vim:sw=4:softtabstop=4:expandtab:set fileencoding=ISO8859-2
#
# Roman.py, part of the FleetPanel
#
# Copyright (c) 2008-2009 Pawe³ 'Reef' Polewicz
# All rights reserved.
#
# This software is licensed as described in the file LICENSE, which
# you should have received as part of this distribution. The terms
# are also available at http://www.opensource.org/licenses/mit-license.php.

# based on http://billmill.org/python_roman.html, I emailed the guy and he said it's licensed under WTFPL, so I wrapped it in a class
# Eve api returns some numbers in Romanian notation
# TODO: We use a reverse translation in a rather unusual way...

class Roman:
    numerals = [("M", 1000), ("CM", 900), ("D", 500), ("CD", 400),
        ("C", 100),  ("XC", 90),  ("L", 50),  ("XL", 40),
        ("X", 10),   ("IX", 9),   ("V", 5),   ("IV", 4),
        ("I", 1)]
    
    @classmethod
    def next(cls, x):
        for n in cls.numerals:
            if n[1] <= x: return (n[0], x-n[1])
    
    @classmethod
    def romanize(cls, n):
        return "".join(cls.unfold(cls.next, n))

    @classmethod
    def unfold(cls, f, x):
        res = [] 
        while 1:
            try:
                w, x = f(x)
                res.append(w)
            except TypeError:
                return res

