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
 'Albert Einstein developed the Theory of Relativity while working at Princeton University in Princeton. Marie Curie pioneered Radioactivity research in Paris and won Nobel Prizes in Physics and Chemistry. Alexander Fleming discovered Penicillin in London, which protects against Tuberculosis and Bacterial Infections. Louis Pasteur developed Vaccination and Pasteurization in Paris, founding Germ Theory. Edward Jenner pioneered Vaccination against Smallpox. Isaac Newton discovered Gravity and Charles Darwin created the theory of Evolution; both studied at the University of Cambridge and were members of the Royal Society in London. Galileo Galilei was a pioneering astronomer in Florence and Rome.',
 ARRAY['Albert Einstein','Marie Curie','Alexander Fleming','Louis Pasteur','Edward Jenner','Isaac Newton','Charles Darwin','Galileo Galilei','Theory of Relativity','Penicillin','Vaccination','Radioactivity','Evolution','Gravity','Pasteurization','Germ Theory','Nobel Foundation','University of Cambridge','Royal Society','Princeton','Princeton University','Paris','London','Florence','Tuberculosis','Bacterial Infections','Smallpox'],
 27, 0.9500),

-- Computer Science & AI community
('benchmark', 'comm-tech-01', 'Computing Pioneers & Artificial Intelligence',
 'Alan Turing, who studied at the University of Cambridge and worked at Bletchley Park on the Enigma Machine, is the father of Artificial Intelligence and Computer Science. Ada Lovelace, based in London, is recognized as the first computer programmer. Tim Berners-Lee created the World Wide Web at CERN. Modern tech companies like Google (connected to Stanford University), Apple Inc, and Microsoft all heavily utilize AI and Machine Learning. The World Wide Web extends the Internet, which evolved from ARPANET.',
 ARRAY['Alan Turing','Ada Lovelace','Tim Berners-Lee','Artificial Intelligence','Computer Science','Machine Learning','Google','Apple Inc','Microsoft','Stanford University','MIT','University of Cambridge','Bletchley Park','Enigma Machine','World Wide Web','CERN','Internet','ARPANET','London','Zurich','Geneva'],
 21, 0.9200),

-- Inventors & Electricity community
('benchmark', 'comm-inventors-01', 'Electrical Pioneers & Industrial Innovation',
 'Nikola Tesla created Electricity systems and Alternating Current in New York City. Thomas Edison, also based in New York City, invented the Light Bulb and championed Direct Current. Tesla and Edison had a famous rivalry. Alexander Graham Bell invented the Telephone. The Steam Engine preceded Electricity as a power source, and Nuclear Energy later became connected to electricity generation. Radioactivity research led to Nuclear Energy developments.',
 ARRAY['Nikola Tesla','Thomas Edison','Alexander Graham Bell','Electricity','Alternating Current','Direct Current','Light Bulb','Telephone','Steam Engine','Nuclear Energy','Radioactivity','New York City'],
 12, 0.8800),

-- World Leaders & Politics community
('benchmark', 'comm-politics-01', 'World Leaders & Political History',
 'Winston Churchill served as British Prime Minister in London during World War II, working closely with Franklin D. Roosevelt in Washington D.C. Napoleon Bonaparte ruled from Paris and had connections to the Louvre Museum. Mahatma Gandhi studied in London before leading India to independence. Nelson Mandela, a Nobel Prize recipient, fought apartheid. Abraham Lincoln governed from Washington D.C. Cleopatra ruled from ancient Cairo.',
 ARRAY['Winston Churchill','Franklin D. Roosevelt','Napoleon Bonaparte','Mahatma Gandhi','Nelson Mandela','Abraham Lincoln','Cleopatra','London','Washington D.C.','Paris','Cairo','Louvre Museum','Nobel Foundation'],
 13, 0.8500),

-- Arts & Culture community
('benchmark', 'comm-arts-01', 'Artists, Writers & Cultural Institutions',
 'Leonardo da Vinci worked in Florence and painted the Mona Lisa, displayed at the Louvre Museum in Paris. William Shakespeare was active in London. Wolfgang Amadeus Mozart was born in Salzburg and later moved to Vienna. Antonio Vivaldi composed the Four Seasons and worked in Rome and Vienna. Pablo Picasso co-founded Cubism, lived in Paris, and has works at the Museo del Prado in Madrid. Vincent van Gogh also worked in Paris. Frida Kahlo''s works have been exhibited at the Louvre. The Metropolitan Museum of Art is in New York City, the British Museum and National Gallery in London, and the Smithsonian Institution in Washington D.C.',
 ARRAY['Leonardo da Vinci','Mona Lisa','William Shakespeare','Wolfgang Amadeus Mozart','Antonio Vivaldi','Pablo Picasso','Vincent van Gogh','Frida Kahlo','Louvre Museum','British Museum','National Gallery','Metropolitan Museum of Art','Smithsonian Institution','Museo del Prado','Florence','Salzburg','Vienna','Madrid','Paris','London','New York City','Washington D.C.'],
 22, 0.9000),

-- Space & Nuclear Research community
('benchmark', 'comm-space-01', 'Space Exploration & Nuclear Research',
 'NASA is headquartered in Washington D.C. and utilizes Nuclear Energy for deep space missions. The European Space Agency is headquartered in Paris. CERN, located near Geneva and Zurich, studies Nuclear Energy and is where Tim Berners-Lee created the World Wide Web. The World Wide Web extends the Internet, which evolved from ARPANET. Radioactivity research led to Nuclear Energy for electricity generation.',
 ARRAY['NASA','European Space Agency','CERN','Tim Berners-Lee','Nuclear Energy','Radioactivity','World Wide Web','Internet','ARPANET','Electricity','Washington D.C.','Paris','Zurich','Geneva'],
 14, 0.8700),

-- Health & Disease community
('benchmark', 'comm-health-01', 'Global Health & Disease Research',
 'The World Health Organization, a subset of the United Nations headquartered in Geneva, studies COVID-19, Malaria, Tuberculosis, Cancer, and Influenza. Vaccination, developed by Louis Pasteur and Edward Jenner, protects against Influenza, COVID-19, and Smallpox. Penicillin, discovered by Alexander Fleming, protects against Tuberculosis and Bacterial Infections. Germ Theory, developed by Pasteur, connects to both Vaccination and Penicillin. Marie Curie''s research on Radioactivity is connected to Cancer research. The chain from Fleming to COVID-19 runs: Fleming created Penicillin, connected to Vaccination, which protects against COVID-19.',
 ARRAY['World Health Organization','United Nations','COVID-19','Malaria','Tuberculosis','Cancer','Influenza','Smallpox','Bacterial Infections','Vaccination','Penicillin','Germ Theory','Pasteurization','Louis Pasteur','Edward Jenner','Alexander Fleming','Marie Curie','Radioactivity','Geneva'],
 19, 0.9100),

-- Film Directors community
('benchmark', 'comm-film-01', 'Film Directors & Cinema',
 'Steven Spielberg and Martin Scorsese are both connected to New York City. Alfred Hitchcock and Stanley Kubrick both worked in London. Frank Tuttle was an American film director. Sergei Yutkevich was a Soviet film director known for biographical films.',
 ARRAY['Steven Spielberg','Alfred Hitchcock','Stanley Kubrick','Martin Scorsese','Frank Tuttle','Sergei Yutkevich','New York City','London'],
 8, 0.7500),

-- Universities & Education community
('benchmark', 'comm-edu-01', 'Major Universities & Research Institutions',
 'MIT and Stanford University are leaders in Artificial Intelligence and Computer Science research. Harvard University is located in Cambridge, Massachusetts. The University of Oxford is in Oxford, connected to London. The University of Cambridge, in the city of Cambridge, England, has educated Isaac Newton, Charles Darwin, and Alan Turing. Princeton University in Princeton was where Albert Einstein worked. Google has strong connections to Stanford University. The Royal Society in London counts Newton and Darwin as members.',
 ARRAY['MIT','Stanford University','Harvard University','University of Oxford','University of Cambridge','Princeton University','Artificial Intelligence','Computer Science','Google','Isaac Newton','Charles Darwin','Alan Turing','Albert Einstein','Royal Society','London','Cambridge','Oxford','Princeton'],
 18, 0.8300)

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
