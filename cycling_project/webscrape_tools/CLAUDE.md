# CLAUDE.md

Database: We have a sqlite database that stores all of our data for this project

Access: Your database access is through the sqlite mcp tool. You can execute sql code through that tool as if you were accessing it through the command line. You want to be careful about not overwhelming your context by setting an appropriate line limit to what you get back. 

Writing Code for Accessing the Database. The code that you write will directly access the database, so you can use your sql code in the python code you write.


We're using uv to run python and manage our environment. Use the `uv run` functionality to run scripts and python commands. 

# Rules for Creating Code

Create simple, modular code. Do not over engineer. Check fo resources in a module or folder that have already been completed to see if they can be reused in an efficient way.