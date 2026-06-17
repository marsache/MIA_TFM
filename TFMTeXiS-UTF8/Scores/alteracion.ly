\version "2.22.1"

melody = \relative c'' {
  \clef treble
  \key d \major 
  \time 6/8
  
  cis8 a a e' fis gis | 
  
  a8 e d cis d b | \bar "||"
}

\score {
  \new Staff { \melody }
  \layout { }
  \midi { }
}