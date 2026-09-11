package com.v3agent.rag.vector.pgvector;

import com.pgvector.PGvector;
import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;

/**
 * JPA 转换器：Java float[] <=> PostgreSQL pgvector vector。
 */
@Converter(autoApply = false)
public class VectorConverter implements AttributeConverter<float[], PGvector> {

    @Override
    public PGvector convertToDatabaseColumn(float[] attribute) {
        if (attribute == null) {
            return null;
        }
        return new PGvector(attribute);
    }

    @Override
    public float[] convertToEntityAttribute(PGvector dbData) {
        if (dbData == null) {
            return null;
        }
        return dbData.toArray();
    }
}
