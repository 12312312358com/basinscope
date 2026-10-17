# Methods

## Collection

The acquisition layer uses province-topic and topic-only queries. Each focal topic
has nine default terms: three negative, three neutral, and three positive. A
default run requests three result pages per keyword, selects up to 50 articles
ranked by comment count for comment retrieval, and retrieves up to five comment
pages per article.

## Text processing and event matching

Chinese text is filtered and segmented with jieba. Topic labels are assigned from
acquisition keywords rather than inferred by an unsupervised topic model. Records
are matched against human-readable event dictionaries. The current module defines
14 overlapping event clusters, so counts are separate matching quantities rather
than additive categories.

## Sentiment calibration

SnowNLP scores are compared with a domain polarity dictionary. The calibration
view reports model behaviour and disagreement. Sentiment scores are structural
references and require domain calibration before use as attitude measures.

## Opinion clustering

TF-IDF and K-means are applied to comment keyword bags. The current cross-platform
snapshot contains 949 comments. Thirteen comments without a matched keyword are
excluded from the keyword-bag clustering input, leaving 936 comments. The current
run produces five clusters with silhouette coefficient 0.464. Cluster labels are
term-derived and exploratory.

## Risk screening

The risk indicator combines four expert-defined normalized factors: negative
share (0.40), event volume (0.25), official-subject sensitivity (0.20), and
diffusion strength (0.15). Events with fewer than 30 matched records are not
graded. Scores are screening indicators, not probabilities or causal estimates.

## Short-video processing

The video pipeline extracts metadata, keyframes, and in-memory audio features.
Automatic speech recognition transcripts are masked for personally identifiable
information, and audio is discarded. The repository does not perform face
recognition, voiceprint extraction, speaker identification, or voice-emotion
recognition.
