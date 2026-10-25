# BasinScope Snapshot Facts

This document summarizes verified snapshot-level facts used by the BasinScope
dashboard and reported in the accompanying manuscript. It is a curated
knowledge document, not a substitute for the source records.

## Corpus and scope

- Current Weibo snapshot: 1,097 articles.
- Focal-topic articles: 899.
- Ecological governance: 371 articles.
- Cultural tourism: 359 articles.
- Healthcare disputes: 169 articles.
- Fallback records excluded from focal-topic analyses: 198.
- Unique authors in the focal-topic Weibo sample: 667.
- Analytical scope: eight Yellow River target provinces (Qinghai, Gansu,
  Ningxia, Inner Mongolia, Shaanxi, Shanxi, Henan, and Shandong).
- Sichuan is displayed on the Yellow River map as a shared Yellow River-Yangtze
  province, but it is assigned to the Yangtze component and is not part of the
  eight-province Yellow River analytical sample.

## Interaction metadata

- Likes: 158,423.
- Comment-count metadata: 32,833. This is distinct from the number of comment
  records actually collected.
- Reposts: 72,681.

## Comments and clustering

- Collected cross-platform comments: 949.
- Platform distribution of collected comments: 59 Weibo, 425 Xiaohongshu,
  465 Zhihu.
- Before clustering, 13 comments shorter than two characters were removed.
- Comments used for TF-IDF and K-means clustering: 936.
- Number of clusters: five.
- Random seed: 42.
- Silhouette coefficient: 0.464. This is an internal diagnostic, not
  classification accuracy.
- The five term-derived cluster sizes are 412, 144, 142, 123, and 115.
- Cluster labels are exploratory. A river-chief-system group appears in the
  shared clustering set, showing that shared keyword clustering does not
  separate ecological-governance and healthcare topics cleanly.

## Sentiment calibration

- Neutral records: 3.6 percent.
- Scores at the extremes: 83.6 percent.
- Agreement between SnowNLP and the domain polarity dictionary: 39.0 percent.
- These scores are used for structural comparison and have not been validated
  as measures of attitude.

## Event and risk screening

- Number of event clusters: 14 overlapping clusters.
- Events with fewer than 30 matched records are shown only as ungraded clues.
- Risk weights: negative share 0.40, volume 0.25, official-subject sensitivity
  0.20, diffusion 0.15. The weights sum to one.
- Central ecological inspection: 139 Weibo articles, 73 negative records,
  52.5 percent negative share, risk score 58.8.
- The 58.8 score contributions are 21.0 for negative share, 16.4 for volume,
  20.0 for official-subject sensitivity, and 1.4 for diffusion.
- Rectification and accountability: 66 articles, risk score 46.1.
- Water pollution and discharge: 56 articles, risk score 35.1.
- Risk grades in the current snapshot: 3 yellow, 9 blue, and 2 clusters below
  the 30-record threshold remain ungraded.
- Risk scores support screening; they are not objective rankings or estimated
  probabilities and have not been externally validated.

## Healthcare-dispute example

- Healthcare-dispute articles: 169 Weibo, 346 Xiaohongshu, and 267 Zhihu.
- Healthcare-dispute comments: 585.
- The healthcare and ecological-governance comments form a combined
  936-comment clustering set.
- Term-derived cluster counts are 412, 144, 142, 123, and 115 comments.
- Silhouette coefficient: 0.464.

## Short-video subset

- Yellow River Douyin cases: 33.
- Topic split: 17 tourism cases and 16 ecological-governance cases.
- All 33 selected cases have keyframes, ASR status `ok`, and non-empty
  transcripts in the current validation set.
- Example case duration: 45.8 seconds.
- Example keyframes: 19.
- Example interaction metadata: 229,780 likes, 40,225 comments, and 460,722
  shares.
- Example ASR transcript length: 212 characters.
- Example software recommendation score: 0.885. This is a software output, not
  an accuracy or causal estimate.

## Interpretation boundaries

- Counts describe the collected snapshot and are not population estimates.
- Platform quotas, uneven comment coverage, and non-random samples limit all
  workflows.
- The system supports exploratory screening and human review, not causal or
  predictive claims.