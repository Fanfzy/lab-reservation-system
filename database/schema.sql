-- 本文件为数据库空结构参考；标准创建入口为manage.py migrate。
-- 不包含演示数据或django_migrations中的版本记录。
PRAGMA foreign_keys=ON; -- 启用外键校验。
CREATE TABLE "auth_group" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(150) NOT NULL UNIQUE); -- 由已迁移模型结构导出。
CREATE TABLE "auth_group_permissions" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "group_id" integer NOT NULL REFERENCES "auth_group" ("id") DEFERRABLE INITIALLY DEFERRED, "permission_id" integer NOT NULL REFERENCES "auth_permission" ("id") DEFERRABLE INITIALLY DEFERRED); -- 由已迁移模型结构导出。
CREATE TABLE "auth_permission" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "content_type_id" integer NOT NULL REFERENCES "django_content_type" ("id") DEFERRABLE INITIALLY DEFERRED, "codename" varchar(100) NOT NULL, "name" varchar(255) NOT NULL); -- 由已迁移模型结构导出。
CREATE TABLE "auth_user" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "password" varchar(128) NOT NULL, "last_login" datetime NULL, "is_superuser" bool NOT NULL, "username" varchar(150) NOT NULL UNIQUE, "last_name" varchar(150) NOT NULL, "email" varchar(254) NOT NULL, "is_staff" bool NOT NULL, "is_active" bool NOT NULL, "date_joined" datetime NOT NULL, "first_name" varchar(150) NOT NULL); -- 由已迁移模型结构导出。
CREATE TABLE "auth_user_groups" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "group_id" integer NOT NULL REFERENCES "auth_group" ("id") DEFERRABLE INITIALLY DEFERRED); -- 由已迁移模型结构导出。
CREATE TABLE "auth_user_user_permissions" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "permission_id" integer NOT NULL REFERENCES "auth_permission" ("id") DEFERRABLE INITIALLY DEFERRED); -- 由已迁移模型结构导出。
CREATE TABLE "django_content_type" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "app_label" varchar(100) NOT NULL, "model" varchar(100) NOT NULL); -- 由已迁移模型结构导出。
CREATE TABLE "django_migrations" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "app" varchar(255) NOT NULL, "name" varchar(255) NOT NULL, "applied" datetime NOT NULL); -- 由已迁移模型结构导出。
CREATE TABLE "django_session" ("session_key" varchar(40) NOT NULL PRIMARY KEY, "session_data" text NOT NULL, "expire_date" datetime NOT NULL); -- 由已迁移模型结构导出。
CREATE TABLE "labapp_auditevent" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "action" varchar(32) NOT NULL, "subject" varchar(120) NOT NULL, "detail" text NOT NULL, "created_at" datetime NOT NULL, "actor_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED); -- 由已迁移模型结构导出。
CREATE TABLE "labapp_lab" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "code" varchar(32) NOT NULL UNIQUE, "name" varchar(100) NOT NULL, "location" varchar(150) NOT NULL, "capacity" integer unsigned NOT NULL CHECK ("capacity" >= 0), "equipment" text NOT NULL, "description" text NOT NULL, "open_time" time NOT NULL, "close_time" time NOT NULL, "is_active" bool NOT NULL, "updated_at" datetime NOT NULL, CONSTRAINT "lab_positive_capacity" CHECK ("capacity" >= 1), CONSTRAINT "lab_valid_hours" CHECK ("close_time" > ("open_time"))); -- 由已迁移模型结构导出。
CREATE TABLE "labapp_reservation" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "start_at" datetime NOT NULL, "end_at" datetime NOT NULL, "purpose" varchar(500) NOT NULL, "attendees" integer unsigned NOT NULL CHECK ("attendees" >= 0), "request_key" char(32) NOT NULL UNIQUE, "status" varchar(12) NOT NULL, "created_at" datetime NOT NULL, "cancelled_at" datetime NULL, "applicant_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "cancelled_by_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "lab_id" bigint NOT NULL REFERENCES "labapp_lab" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "booking_valid_interval" CHECK ("end_at" > ("start_at")), CONSTRAINT "booking_positive_attendees" CHECK ("attendees" >= 1), CONSTRAINT "booking_valid_status" CHECK ("status" IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED'))); -- 由已迁移模型结构导出。
CREATE TABLE "labapp_reviewrecord" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "approved" bool NOT NULL, "reason" varchar(500) NOT NULL, "reviewed_at" datetime NOT NULL, "reservation_id" bigint NOT NULL UNIQUE REFERENCES "labapp_reservation" ("id") DEFERRABLE INITIALLY DEFERRED, "reviewer_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED); -- 由已迁移模型结构导出。
CREATE INDEX "auth_group_permissions_group_id_b120cbf9" ON "auth_group_permissions" ("group_id"); -- 由已迁移模型结构导出。
CREATE UNIQUE INDEX "auth_group_permissions_group_id_permission_id_0cd325b0_uniq" ON "auth_group_permissions" ("group_id", "permission_id"); -- 由已迁移模型结构导出。
CREATE INDEX "auth_group_permissions_permission_id_84c5c92e" ON "auth_group_permissions" ("permission_id"); -- 由已迁移模型结构导出。
CREATE INDEX "auth_permission_content_type_id_2f476e4b" ON "auth_permission" ("content_type_id"); -- 由已迁移模型结构导出。
CREATE UNIQUE INDEX "auth_permission_content_type_id_codename_01ab375a_uniq" ON "auth_permission" ("content_type_id", "codename"); -- 由已迁移模型结构导出。
CREATE INDEX "auth_user_groups_group_id_97559544" ON "auth_user_groups" ("group_id"); -- 由已迁移模型结构导出。
CREATE INDEX "auth_user_groups_user_id_6a12ed8b" ON "auth_user_groups" ("user_id"); -- 由已迁移模型结构导出。
CREATE UNIQUE INDEX "auth_user_groups_user_id_group_id_94350c0c_uniq" ON "auth_user_groups" ("user_id", "group_id"); -- 由已迁移模型结构导出。
CREATE INDEX "auth_user_user_permissions_permission_id_1fbb5f2c" ON "auth_user_user_permissions" ("permission_id"); -- 由已迁移模型结构导出。
CREATE INDEX "auth_user_user_permissions_user_id_a95ead1b" ON "auth_user_user_permissions" ("user_id"); -- 由已迁移模型结构导出。
CREATE UNIQUE INDEX "auth_user_user_permissions_user_id_permission_id_14a6b632_uniq" ON "auth_user_user_permissions" ("user_id", "permission_id"); -- 由已迁移模型结构导出。
CREATE INDEX "booking_occupancy_idx" ON "labapp_reservation" ("lab_id", "status", "start_at"); -- 由已迁移模型结构导出。
CREATE INDEX "booking_owner_date_idx" ON "labapp_reservation" ("applicant_id", "start_at"); -- 由已迁移模型结构导出。
CREATE UNIQUE INDEX "django_content_type_app_label_model_76bd3d3b_uniq" ON "django_content_type" ("app_label", "model"); -- 由已迁移模型结构导出。
CREATE INDEX "django_session_expire_date_a5c62663" ON "django_session" ("expire_date"); -- 由已迁移模型结构导出。
CREATE INDEX "labapp_auditevent_actor_id_b997376e" ON "labapp_auditevent" ("actor_id"); -- 由已迁移模型结构导出。
CREATE INDEX "labapp_reservation_applicant_id_96b93e79" ON "labapp_reservation" ("applicant_id"); -- 由已迁移模型结构导出。
CREATE INDEX "labapp_reservation_cancelled_by_id_b6284ba3" ON "labapp_reservation" ("cancelled_by_id"); -- 由已迁移模型结构导出。
CREATE INDEX "labapp_reservation_lab_id_2f42acc5" ON "labapp_reservation" ("lab_id"); -- 由已迁移模型结构导出。
CREATE INDEX "labapp_reviewrecord_reviewer_id_15d8d53a" ON "labapp_reviewrecord" ("reviewer_id"); -- 由已迁移模型结构导出。
