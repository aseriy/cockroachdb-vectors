CREATE OR REPLACE FUNCTION clear_vector_on_source_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$

BEGIN
    IF (NEW).passage <> (OLD).passage THEN
        NEW.passage_vector := NULL;
        NEW.passage_openai := NULL;
    END IF;

    RETURN NEW;
END;
$$;



CREATE TRIGGER clear_vector_on_source_change
    BEFORE UPDATE ON passage
    FOR EACH ROW
    EXECUTE FUNCTION clear_vector_on_source_change();

