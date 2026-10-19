# R2 — the all-particles family_base divergence

R2. Rationale: callers need the surname with and without its
    particles — sorting wants "Vega", display wants "de la Vega".
    The family name splits into further views: the base (the family
    without its leading particles) and the particles themselves. A
    name part whose every word is particle vocabulary is a part where
    none of them is doing a particle's work — nothing joins them to a
    name — so they read as ordinary name words: they anchor the base
    and leave the particles view. "Every word", not "standing alone":
    a two-particle run has neither word alone and both are name words
    there. Position decides that, not vocabulary; whether the word is
    borne as a surname somewhere does not enter into it.
      "Dr. Juan Q. Xavier de la Vega III"  →  family_base="Vega"
      "Dr. Juan Q. Xavier de la Vega III"  →  family_particles="de la"
      "Anh Do"                    →  family_base="Do"
      "Juan van der"              →  family_base="van der"
      "Juan van der"              →  family_particles=""
      "Juan de la Vega"           →  family_base="Vega"  · boundary
      "Juan de la Vega"           →  family_particles="de la"
      "Sean O'Connor"             →  family_base="O'Connor"
    Accepted, and the invariant it exists to hold: a non-empty
    family always has a non-empty base. A particle needs a base to
    attach to, so a family that is all particles is a family whose
    words are not acting as particles.
      "Del Toro"  family-first    →  family_base="Del"
    Accepted: the test runs after every rule that moves a token
    between parts, so O3's fold decides it too — a middle folded into
    the family can leave the family all particles, or can give a
    trailing particle the name word it was missing.
      "Anh Van Do"  middle_as_family  →  family_base="Van Do"
      "Nguyen, Van Le"  middle_as_family  →  family_particles="Le"
    Signal: a neighbor: a family part whose every word is particle vocabulary
    history: decisions/R2 · interacts: R3 · implemented: nameparser/_types.py, nameparser/_pipeline/_post_rules.py, nameparser/_facade.py

