config = [
    {
        'input': 'passage',
        'output': ['passage_vector', 'passage_openai']
    },
    {
        'input': 'description',
        'output': ['description_hf', 'description_openai']
    }
]



CREATE OR REPLACE FUNCTION clear_vector_on_source_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$

BEGIN
    IF (NEW).passage <> (OLD).passage THEN
        NEW.passage_vector := NULL;
        NEW.passage_openai := NULL;
    END IF;

    IF (NEW).description <> (OLD).description THEN
        NEW.description_hf := NULL;
        NEW.description_openai := NULL;
    END IF;

    RETURN NEW;
END;
$$;


CREATE TRIGGER clear_vector_on_source_change
    BEFORE UPDATE ON passage
    FOR EACH ROW
    EXECUTE FUNCTION clear_vector_on_source_change();




CREATE OR REPLACE FUNCTION clear_vector_on_source_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$

BEGIN
    {% for item in config %}
    IF (NEW).{{ item.input }} <> (OLD).{{ item.input }} THEN
        {% for out in item.output %}
        NEW.{{ out }} := NULL;
        {% endfor %}
    END IF;

    {% endfor %}
    RETURN NEW;
END;
$$;