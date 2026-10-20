# W2 — the glued-honorific peel

**When:** an East Asian honorific is glued directly onto the end of a name, as in "田中さん".

**Then:** a listed honorific glued to the end of the name's last name word splits off once and reads as a suffix.

- **A part that is not name text — a post-nominal word standing on its own — is never the name's end**: the split-off steps past it to the name word behind, and never dissects it.
  ```
  "김민준 박사님"             →  suffix="박사님"
  "선생님"                    →  family="선생님"  · boundary
  ```

**Because:** a glued word peels off only if it could never itself end a name, so the listed vocabulary carries its own license and needs no other gate.

```
"田中さん"                  →  suffix="さん"
"김민준씨"                  →  suffix="씨"
"马丁·路德·金씨"            →  suffix="씨"
"田中 社長"                 →  suffix="社長"
"田中社長"                  →  suffix="社長"
"陳怡君二世"                →  suffix="二世"
"김지양"                    →  suffix=""  · boundary
"王君"                      →  family="王君"  · boundary
```

**Accepted:**

- 部長 and its simplified spelling 部长 are vocabulary in the spaced and after-comma positions only, and no peel splits them off a glued name: 田中部長 keeps the word in the name, because 長 alone is a borne given name and 阿部長 can be 阿部 + 長. The other credential, office and generational words of #671 (議員, 国会議員, 太平紳士, 医学博士, 二世, 社長, 課長 and their variant spellings) met the glued bar when measured against real names (#707) and peel. The Han segmenter's own division is not a peel and exposes 部長 regardless: under the Chinese pack a listed surname followed by it divides there and the word reads as a suffix, so 李部長 reads family 李, suffix 部長, as 王博士 already does.
  ```
  "田中部長"                  →  family="田中部長"  · boundary
  ```
- A longer office or degree word that ends in a listed tail is split at it, whether glued or spaced, because the tail is matched at the end of the token and the longer word is not listed: 衆議院議員, 副社長, 代表取締役社長 and 獣医学博士 leave their head (衆議院, 副, 代表取締役, 獣) in the name. Before the tail was listed the whole word stayed in the name, which was no more right (#707).
  ```
  "田中 副社長"               →  given="副"
  "岸田文雄衆議院議員"        →  family="岸田文雄衆議院"
  ```

---
**Signal:** neighbor: a listed honorific glued to the end of the name's last name word
**history:** decisions/W2 · **implemented:** nameparser/_pipeline/_script_segment.py
