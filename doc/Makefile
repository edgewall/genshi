HTML_FILES = \
	builder.html \
	index.html \
	streams.html \
	xml-templates.html \
	xpath.html

all: $(HTML_FILES)

%.html: %.txt
	rst2html.py --exit-status=3 $< $@

clean:
	rm -rf $(HTML_FILES)
