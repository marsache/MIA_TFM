\version "2.22.1"

melody = \relative c'' {
  \clef treble
  \key c \major
  \time 4/4
  
  g4 a b \once \stemUp c |
  
    d4 b g c \bar "|."
}

\score {
  \new Staff { \melody }
  \layout { }
  \midi { }
}