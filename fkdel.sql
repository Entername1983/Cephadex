

ALTER TABLE distribution
DROP FOREIGN KEY distribution_ibfk_1;
ALTER TABLE distribution
ADD CONSTRAINT distribution_ibfk_1
FOREIGN KEY (taker_id) REFERENCES user (id) ON DELETE SET NULL;

ALTER TABLE event_tracking
DROP FOREIGN KEY event_tracking_ibfk_1;
ALTER TABLE event_tracking
ADD CONSTRAINT event_tracking_ibfk_1
FOREIGN KEY (user) REFERENCES user (id) ON DELETE SET NULL;

ALTER TABLE job
DROP FOREIGN KEY job_ibfk_1;
ALTER TABLE job
ADD CONSTRAINT job_ibfk_1
FOREIGN KEY (user) REFERENCES user (id) ON DELETE SET NULL;



ALTER TABLE shared_decks
DROP FOREIGN KEY shared_decks_ibfk_1;
ALTER TABLE shared_decks
ADD CONSTRAINT shared_decks_ibfk_1
FOREIGN KEY (sender) REFERENCES user (id) ON DELETE SET NULL;

ALTER TABLE shared_decks
DROP FOREIGN KEY shared_decks_ibfk_2;
ALTER TABLE shared_decks
ADD CONSTRAINT shared_decks_ibfk_2
FOREIGN KEY (receiver) REFERENCES user (id) ON DELETE SET NULL;


ALTER TABLE test_result
DROP FOREIGN KEY test_result_ibfk_1;
ALTER TABLE test_result
ADD CONSTRAINT test_result_ibfk_1
FOREIGN KEY (taker) REFERENCES user (id) ON DELETE SET NULL;

ALTER TABLE test_result
DROP FOREIGN KEY test_result_ibfk_2;
ALTER TABLE test_result
ADD CONSTRAINT test_result_ibfk_2
FOREIGN KEY (creator) REFERENCES user (id) ON DELETE SET NULL;



ALTER TABLE user_settings
DROP FOREIGN KEY user_settings_ibfk_1;
ALTER TABLE user_settings
ADD CONSTRAINT user_settings_ibfk_1
FOREIGN KEY (user) REFERENCES user (id) ON DELETE SET NULL;

ALTER TABLE test
DROP FOREIGN KEY test_ibfk_1;
ALTER TABLE test
ADD CONSTRAINT test_ibfk_1
FOREIGN KEY (creator) REFERENCES user (id) ON DELETE SET NULL;

ALTER TABLE usage_records
DROP FOREIGN KEY usage_records_ibfk_1;
ALTER TABLE usage_records
ADD CONSTRAINT usage_records_ibfk_1
FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE SET NULL;