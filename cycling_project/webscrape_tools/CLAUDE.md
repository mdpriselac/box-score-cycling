# CLAUDE.md

Database location: the database we're working with is at database/database/cycling_races.db
Database type: sqlite
Database Structure and Access Information: db_migration_update_1.md

You can use sqlite to directly access and test the database.

We're using uv to run python and manage our environment. Use the `uv run` functionality to run scripts and python commands. 

# Rules for Creating Code

Whenever you create a module or python file that is not just just for testing but to house code that will be imported elsewhere you must also create a markdown file with the exact same name as the python file followed.by the .md suffix instead of the .py suffix. The guide should be a succinct summary of the classes and functinos in the file with the exact names and argument formats for any methods or inputs to functions. Someone should be able to read the markdown file alone and be able to use the classes and functions in their code without committing any errors in their code.

Whenever you are importing code from a file, make sure you check the corresponding markdown file before writing any code so that you know exactly the right class names, methods and functions as well as the inputs for those files.

You must follow this python-markdown pairing for all code you write.