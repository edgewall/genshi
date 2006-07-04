<!DOCTYPE html
    PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
  <head>
    <title><?cs var:title ?></title>
  </head>
  <body>
    <?cs include:"header.cs" ?>
    
    <h2>Loop</h2>
    <?cs if:len(items) ?>
      <ul>
        <?cs each:item = items ?>
          <li><?cs var:item ?></li>
        <?cs /each ?>
      </ul>
    <?cs /if ?>
    
    <?cs include:"footer.cs" ?>
  </body>
</html>
