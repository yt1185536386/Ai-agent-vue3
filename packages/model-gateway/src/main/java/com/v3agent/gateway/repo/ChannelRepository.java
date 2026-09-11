package com.v3agent.gateway.repo;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface ChannelRepository extends JpaRepository<ChannelEntity, String> {

    List<ChannelEntity> findByStatusOrderByPriorityAsc(Integer status);

    /** 按渠道 key(如 company / bailian)查找,对应调用方 X-Channel-Key 头 */
    Optional<ChannelEntity> findByChannelKey(String channelKey);
}
