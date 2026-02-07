-- ============================================================
-- Community Summaries table for Graph RAG (WF2 V3.3)
--
-- WF2 queries this table via the "Community Summaries Fetch" node:
--   SELECT summary, relevance_score, entity_names
--   FROM community_summaries
--   WHERE entity_names && ARRAY[...]::text[]
--     AND tenant_id = '...'
--
-- Without this table, the node errors silently (onError: continueErrorOutput)
-- and Graph RAG misses community context.
-- ============================================================

-- Drop existing table to ensure correct schema (re-runnable)
DROP TABLE IF EXISTS community_summaries CASCADE;

CREATE TABLE IF NOT EXISTS community_summaries (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'benchmark',
    community_id TEXT NOT NULL,
    title TEXT,
    summary TEXT NOT NULL,
    entity_names TEXT[] NOT NULL DEFAULT '{}',
    entity_count INT DEFAULT 0,
    relevance_score NUMERIC(5,4) DEFAULT 0.5,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, community_id)
);

CREATE INDEX IF NOT EXISTS idx_cs_tenant ON community_summaries(tenant_id);
CREATE INDEX IF NOT EXISTS idx_cs_entities ON community_summaries USING GIN(entity_names);
CREATE INDEX IF NOT EXISTS idx_cs_relevance ON community_summaries(relevance_score DESC);

-- ============================================================
-- Seed community summaries from the curated entity graph
-- These match the entities created by populate-neo4j-entities.py
-- ============================================================

INSERT INTO community_summaries (tenant_id, community_id, title, summary, entity_names, entity_count, relevance_score)
VALUES
-- Science & Discovery community
('benchmark', 'comm-science-01', 'Scientific Pioneers & Nobel Laureates',
 'Albert Einstein developed the Theory of Relativity while working at Princeton. Marie Curie pioneered radioactivity research in Paris and won Nobel Prizes in Physics and Chemistry. Alexander Fleming discovered Penicillin, which protects against Tuberculosis. Louis Pasteur developed Vaccination in Paris. Isaac Newton and Charles Darwin both studied at the University of Cambridge and were members of the Royal Society in London.',
 ARRAY['Albert Einstein','Marie Curie','Alexander Fleming','Louis Pasteur','Isaac Newton','Charles Darwin','Theory of Relativity','Penicillin','Vaccination','Nobel Foundation','University of Cambridge','Royal Society','Princeton','Paris','London'],
 15, 0.9500),

-- Computer Science & AI community
('benchmark', 'comm-tech-01', 'Computing Pioneers & Artificial Intelligence',
 'Alan Turing, who studied at the University of Cambridge, is considered the father of Artificial Intelligence and theoretical computer science. Ada Lovelace, based in London, is recognized as the first computer programmer. Modern tech companies like Google (connected to Stanford University), Apple Inc, and Microsoft all heavily utilize AI. The World Wide Web was created at CERN in Zurich and extends the Internet.',
 ARRAY['Alan Turing','Ada Lovelace','Artificial Intelligence','Google','Apple Inc','Microsoft','Stanford University','MIT','University of Cambridge','World Wide Web','CERN','Internet','London','Zurich'],
 14, 0.9200),

-- Inventors & Electricity community
('benchmark', 'comm-inventors-01', 'Electrical Pioneers & Industrial Innovation',
 'Nikola Tesla created foundational work on Electricity and alternating current systems in New York City. Thomas Edison, also based in New York City, utilized Electricity for inventions including the light bulb and was connected to the Telephone. Tesla and Edison had a famous rivalry. The Steam Engine preceded Electricity as a power source, and Nuclear Energy later became connected to electricity generation.',
 ARRAY['Nikola Tesla','Thomas Edison','Electricity','Telephone','Steam Engine','Nuclear Energy','New York City'],
 7, 0.8800),

-- World Leaders & Politics community
('benchmark', 'comm-politics-01', 'World Leaders & Political History',
 'Winston Churchill served as British Prime Minister in London during World War II, working closely with Franklin D. Roosevelt in Washington D.C. Napoleon Bonaparte ruled from Paris and had connections to the Louvre Museum. Mahatma Gandhi studied in London before leading India to independence. Nelson Mandela, a Nobel Prize recipient, fought apartheid. Abraham Lincoln governed from Washington D.C. Cleopatra ruled from ancient Cairo.',
 ARRAY['Winston Churchill','Franklin D. Roosevelt','Napoleon Bonaparte','Mahatma Gandhi','Nelson Mandela','Abraham Lincoln','Cleopatra','London','Washington D.C.','Paris','Cairo','Louvre Museum','Nobel Foundation'],
 13, 0.8500),

-- Arts & Culture community
('benchmark', 'comm-arts-01', 'Artists, Writers & Cultural Institutions',
 'Leonardo da Vinci worked in Florence and his works are displayed at the Louvre Museum in Paris. William Shakespeare was active in London. Wolfgang Amadeus Mozart was born in Salzburg and later moved to Vienna. Pablo Picasso lived in Paris and has works at the Museo del Prado. Vincent van Gogh also worked in Paris. Frida Kahlo''s works have been exhibited at the Louvre. The Metropolitan Museum of Art is located in New York City, the British Museum in London, and the Smithsonian Institution in Washington D.C.',
 ARRAY['Leonardo da Vinci','William Shakespeare','Wolfgang Amadeus Mozart','Pablo Picasso','Vincent van Gogh','Frida Kahlo','Louvre Museum','British Museum','Metropolitan Museum of Art','Smithsonian Institution','Museo del Prado','Florence','Salzburg','Vienna','Paris','London','New York City','Washington D.C.'],
 18, 0.9000),

-- Space & Nuclear Research community
('benchmark', 'comm-space-01', 'Space Exploration & Nuclear Research',
 'NASA is headquartered in Washington D.C. and utilizes Nuclear Energy for deep space missions. The European Space Agency is based in Paris. CERN, located near Zurich, studies Nuclear Energy and is where the World Wide Web was created. The World Wide Web extends the Internet, which was originally developed for research communication.',
 ARRAY['NASA','European Space Agency','CERN','Nuclear Energy','World Wide Web','Internet','Washington D.C.','Paris','Zurich'],
 9, 0.8700),

-- Health & Disease community
('benchmark', 'comm-health-01', 'Global Health & Disease Research',
 'The World Health Organization, a subset of the United Nations, studies COVID-19, Malaria, Tuberculosis, and Cancer. Vaccination, developed by Louis Pasteur, protects against Influenza and COVID-19. Penicillin, discovered by Alexander Fleming, protects against Tuberculosis. Marie Curie''s research on radioactivity is connected to Cancer research.',
 ARRAY['World Health Organization','United Nations','COVID-19','Malaria','Tuberculosis','Cancer','Influenza','Vaccination','Penicillin','Louis Pasteur','Alexander Fleming','Marie Curie'],
 12, 0.9100),

-- Film Directors community
('benchmark', 'comm-film-01', 'Film Directors & Cinema',
 'Steven Spielberg and Martin Scorsese are both connected to New York City. Alfred Hitchcock and Stanley Kubrick both worked in London. Frank Tuttle was an American film director. Sergei Yutkevich was a Soviet film director known for biographical films.',
 ARRAY['Steven Spielberg','Alfred Hitchcock','Stanley Kubrick','Martin Scorsese','Frank Tuttle','Sergei Yutkevich','New York City','London'],
 8, 0.7500),

-- Universities & Education community
('benchmark', 'comm-edu-01', 'Major Universities & Research Institutions',
 'MIT and Stanford University are leaders in Artificial Intelligence research. Harvard University is located near Cambridge. The University of Oxford is connected to London. The University of Cambridge has educated Isaac Newton, Charles Darwin, and Alan Turing. Google has strong connections to Stanford University.',
 ARRAY['MIT','Stanford University','Harvard University','University of Oxford','University of Cambridge','Artificial Intelligence','Google','Isaac Newton','Charles Darwin','Alan Turing','London'],
 11, 0.8300)

ON CONFLICT (tenant_id, community_id) DO UPDATE SET
    summary = EXCLUDED.summary,
    entity_names = EXCLUDED.entity_names,
    entity_count = EXCLUDED.entity_count,
    relevance_score = EXCLUDED.relevance_score;

-- Verify
SELECT community_id, title, entity_count, relevance_score
FROM community_summaries
WHERE tenant_id = 'benchmark'
ORDER BY relevance_score DESC;
