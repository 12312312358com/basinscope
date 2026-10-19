-- Schema-only review database for Yuyan-Yellow River.
-- Contains no platform records, credentials, or personal data.
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS `t_douyin_comment`;
DROP TABLE IF EXISTS `t_douyin_article`;
DROP TABLE IF EXISTS `t_zhihu_comment`;
DROP TABLE IF EXISTS `t_zhihu_article`;
DROP TABLE IF EXISTS `t_xhs_comment`;
DROP TABLE IF EXISTS `t_xhs_article`;
DROP TABLE IF EXISTS `t_basin_comment`;
DROP TABLE IF EXISTS `t_basin_article`;
DROP TABLE IF EXISTS `t_comment`;
DROP TABLE IF EXISTS `t_article`;
DROP TABLE IF EXISTS `t_user`;

-- t_user
CREATE TABLE `t_user` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(20) DEFAULT NULL,
  `password` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `createtime` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=42 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- t_article
CREATE TABLE `t_article` (
  `微博ID` bigint DEFAULT NULL,
  `微博内容` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `转发数` bigint DEFAULT NULL,
  `评论数` bigint DEFAULT NULL,
  `点赞数` bigint DEFAULT NULL,
  `发布地区` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `发布时间` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `分类` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `微博链接` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `作者ID` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `作者昵称` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `作者主页` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- t_comment
CREATE TABLE `t_comment` (
  `评论ID` bigint DEFAULT NULL,
  `评论内容` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `评论时间` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `来源` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `点赞数` bigint DEFAULT NULL,
  `微博ID` bigint DEFAULT NULL,
  `用户ID` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `昵称` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `性别` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `用户主页` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- t_basin_article
CREATE TABLE `t_basin_article` (
  `微博ID` bigint NOT NULL,
  `微博内容` text,
  `转发数` bigint DEFAULT '0',
  `评论数` bigint DEFAULT '0',
  `点赞数` bigint DEFAULT '0',
  `发布地区` text,
  `发布时间` text,
  `分类` text,
  `微博链接` text,
  `作者ID` text,
  `作者昵称` text,
  `作者主页` text,
  `流域` varchar(16) DEFAULT NULL,
  `议题` varchar(32) DEFAULT NULL,
  `命中关键词` varchar(255) DEFAULT NULL,
  `目标省份` varchar(16) DEFAULT NULL,
  `采集时间` datetime DEFAULT NULL,
  PRIMARY KEY (`微博ID`),
  KEY `idx_basin` (`流域`),
  KEY `idx_topic` (`议题`),
  KEY `idx_pubtime` (`发布时间`(32))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- t_basin_comment
CREATE TABLE `t_basin_comment` (
  `评论ID` bigint NOT NULL,
  `评论内容` text,
  `评论时间` text,
  `来源` text,
  `点赞数` bigint DEFAULT '0',
  `微博ID` bigint DEFAULT NULL,
  `用户ID` text,
  `昵称` text,
  `性别` text,
  `用户主页` text,
  `流域` varchar(16) DEFAULT NULL,
  `议题` varchar(32) DEFAULT NULL,
  `命中关键词` varchar(255) DEFAULT NULL,
  `采集时间` datetime DEFAULT NULL,
  PRIMARY KEY (`评论ID`),
  KEY `idx_basin` (`流域`),
  KEY `idx_weibo` (`微博ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- t_xhs_article
CREATE TABLE `t_xhs_article` (
  `内容ID` varchar(96) NOT NULL,
  `标题` text,
  `正文` text,
  `话题标签` text,
  `点赞数` bigint DEFAULT '0',
  `评论数` bigint DEFAULT '0',
  `收藏数` bigint DEFAULT '0',
  `分享数` bigint DEFAULT '0',
  `详情链接` text,
  `封面` text,
  `发布地区` varchar(32) DEFAULT NULL,
  `发布时间` text,
  `作者ID` varchar(64) DEFAULT NULL,
  `作者昵称` text,
  `作者主页` varchar(128) DEFAULT NULL,
  `平台` varchar(8) DEFAULT NULL,
  `流域` varchar(16) DEFAULT NULL,
  `议题` varchar(32) DEFAULT NULL,
  `命中关键词` varchar(255) DEFAULT NULL,
  `目标省份` varchar(16) DEFAULT NULL,
  `采集时间` datetime DEFAULT NULL,
  PRIMARY KEY (`内容ID`),
  KEY `idx_platform` (`平台`),
  KEY `idx_basin` (`流域`),
  KEY `idx_topic` (`议题`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- t_xhs_comment
CREATE TABLE `t_xhs_comment` (
  `评论ID` varchar(96) NOT NULL,
  `评论内容` text,
  `评论时间` text,
  `点赞数` bigint DEFAULT '0',
  `回复数` bigint DEFAULT '0',
  `内容ID` varchar(96) DEFAULT NULL,
  `用户ID` varchar(64) DEFAULT NULL,
  `昵称` text,
  `性别` varchar(8) DEFAULT NULL,
  `用户地区` varchar(32) DEFAULT NULL,
  `用户主页` varchar(128) DEFAULT NULL,
  `平台` varchar(8) DEFAULT NULL,
  `流域` varchar(16) DEFAULT NULL,
  `议题` varchar(32) DEFAULT NULL,
  `命中关键词` varchar(255) DEFAULT NULL,
  `采集时间` datetime DEFAULT NULL,
  PRIMARY KEY (`评论ID`),
  KEY `idx_content` (`内容ID`),
  KEY `idx_basin` (`流域`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- t_zhihu_article
CREATE TABLE `t_zhihu_article` (
  `内容ID` varchar(96) NOT NULL,
  `标题` text,
  `正文` text,
  `话题标签` text,
  `点赞数` bigint DEFAULT '0',
  `评论数` bigint DEFAULT '0',
  `收藏数` bigint DEFAULT '0',
  `分享数` bigint DEFAULT '0',
  `详情链接` text,
  `封面` text,
  `发布地区` varchar(32) DEFAULT NULL,
  `发布时间` text,
  `作者ID` varchar(64) DEFAULT NULL,
  `作者昵称` text,
  `作者主页` varchar(128) DEFAULT NULL,
  `平台` varchar(8) DEFAULT NULL,
  `流域` varchar(16) DEFAULT NULL,
  `议题` varchar(32) DEFAULT NULL,
  `命中关键词` varchar(255) DEFAULT NULL,
  `目标省份` varchar(16) DEFAULT NULL,
  `采集时间` datetime DEFAULT NULL,
  PRIMARY KEY (`内容ID`),
  KEY `idx_platform` (`平台`),
  KEY `idx_basin` (`流域`),
  KEY `idx_topic` (`议题`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- t_zhihu_comment
CREATE TABLE `t_zhihu_comment` (
  `评论ID` varchar(96) NOT NULL,
  `评论内容` text,
  `评论时间` text,
  `点赞数` bigint DEFAULT '0',
  `回复数` bigint DEFAULT '0',
  `内容ID` varchar(96) DEFAULT NULL,
  `用户ID` varchar(64) DEFAULT NULL,
  `昵称` text,
  `性别` varchar(8) DEFAULT NULL,
  `用户地区` varchar(32) DEFAULT NULL,
  `用户主页` varchar(128) DEFAULT NULL,
  `平台` varchar(8) DEFAULT NULL,
  `流域` varchar(16) DEFAULT NULL,
  `议题` varchar(32) DEFAULT NULL,
  `命中关键词` varchar(255) DEFAULT NULL,
  `采集时间` datetime DEFAULT NULL,
  PRIMARY KEY (`评论ID`),
  KEY `idx_content` (`内容ID`),
  KEY `idx_basin` (`流域`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- t_douyin_article
CREATE TABLE `t_douyin_article` (
  `视频ID` varchar(64) NOT NULL,
  `视频标题` text,
  `视频描述` text,
  `话题标签` text,
  `点赞数` bigint DEFAULT '0',
  `评论数` bigint DEFAULT '0',
  `收藏数` bigint DEFAULT '0',
  `分享数` bigint DEFAULT '0',
  `发布地区` varchar(32) DEFAULT NULL,
  `发布时间` text,
  `作者ID` varchar(64) DEFAULT NULL,
  `作者昵称` text,
  `作者主页` varchar(128) DEFAULT NULL,
  `视频链接` text,
  `平台` varchar(8) DEFAULT '抖音',
  `流域` varchar(16) DEFAULT NULL,
  `议题` varchar(32) DEFAULT NULL,
  `命中关键词` varchar(255) DEFAULT NULL,
  `目标省份` varchar(16) DEFAULT NULL,
  `采集时间` datetime DEFAULT NULL,
  `时长秒` float DEFAULT NULL COMMENT '视频时长（秒）',
  `分辨率` varchar(16) DEFAULT NULL COMMENT '如 1080x1920',
  `播放地址` text COMMENT 'aweme.video.play_addr（带签名、有时效）',
  `封面` text COMMENT 'aweme.video.cover 首图地址',
  PRIMARY KEY (`视频ID`),
  KEY `idx_basin` (`流域`),
  KEY `idx_topic` (`议题`),
  KEY `idx_platform` (`平台`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- t_douyin_comment
CREATE TABLE `t_douyin_comment` (
  `评论ID` varchar(64) NOT NULL,
  `评论内容` text,
  `评论时间` text,
  `点赞数` bigint DEFAULT '0',
  `回复数` bigint DEFAULT '0',
  `视频ID` varchar(64) DEFAULT NULL,
  `用户ID` varchar(64) DEFAULT NULL,
  `昵称` text,
  `性别` varchar(8) DEFAULT NULL,
  `用户地区` varchar(32) DEFAULT NULL,
  `用户主页` varchar(128) DEFAULT NULL,
  `平台` varchar(8) DEFAULT '抖音',
  `流域` varchar(16) DEFAULT NULL,
  `议题` varchar(32) DEFAULT NULL,
  `命中关键词` varchar(255) DEFAULT NULL,
  `采集时间` datetime DEFAULT NULL,
  PRIMARY KEY (`评论ID`),
  KEY `idx_video` (`视频ID`),
  KEY `idx_basin` (`流域`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
SET FOREIGN_KEY_CHECKS = 1;
