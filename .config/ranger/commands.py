# This is a sample commands.py.  You can add your own commands here.
#
# Please refer to commands_full.py for all the default commands and a complete
# documentation.  Do NOT add them all here, or you may end up with defunct
# commands when upgrading ranger.

# A simple command for demonstration purposes follows.
# -----------------------------------------------------------------------------

from __future__ import (absolute_import, division, print_function)

# You can import any python module as needed.
import os

# You always need to import ranger.api.commands here to get the Command class:
from ranger.api.commands import Command


# Any class that is a subclass of "Command" will be integrated into ranger as a
# command.  Try typing ":my_edit<ENTER>" in ranger!
#class my_edit(Command):
#    # The so-called doc-string of the class will be visible in the built-in
#    # help that is accessible by typing "?c" inside ranger.
#    """:my_edit <filename>
#
#    A sample command for demonstration purposes that opens a file in an editor.
#    """
#
#    # The execute method is called when you run this command in ranger.
#    def execute(self):
#        # self.arg(1) is the first (space-separated) argument to the function.
#        # This way you can write ":my_edit somefilename<ENTER>".
#        if self.arg(1):
#            # self.rest(1) contains self.arg(1) and everything that follows
#            target_filename = self.rest(1)
#        else:
#            # self.fm is a ranger.core.filemanager.FileManager object and gives
#            # you access to internals of ranger.
#            # self.fm.thisfile is a ranger.container.file.File object and is a
#            # reference to the currently selected file.
#            target_filename = self.fm.thisfile.path
#
#        # This is a generic function to print text in ranger.
#        self.fm.notify("Let's edit the file " + target_filename + "!")
#
#        # Using bad=True in fm.notify allows you to print error messages:
#        if not os.path.exists(target_filename):
#            self.fm.notify("The given file does not exist!", bad=True)
#            return
#
#        # This executes a function from ranger.core.acitons, a module with a
#        # variety of subroutines that can help you construct commands.
#        # Check out the source, or run "pydoc ranger.core.actions" for a list.
#        self.fm.edit_file(target_filename)
#
#    # The tab method is called when you press tab, and should return a list of
#    # suggestions that the user will tab through.
#    # tabnum is 1 for <TAB> and -1 for <S-TAB> by default
#    def tab(self, tabnum):
#        # This is a generic tab-completion function that iterates through the
#        # content of the current directory.
#        return self._tab_directory_content()



# Select a location using fzf
# Source: https://github.com/ranger/ranger/wiki/Custom-Commands#fzf-integration
class fzf_select(Command):
    """
    :fzf_select
    Find a file using fzf.
    With a prefix argument to select only directories.

    See: https://github.com/junegunn/fzf
    """

    def execute(self):
        import subprocess
        import os
        from ranger.ext.get_executables import get_executables

        if 'fzf' not in get_executables():
            self.fm.notify('Could not find fzf in the PATH.', bad=True)
            return

        fd = None
        if 'fdfind' in get_executables():
            fd = 'fdfind'
        elif 'fd' in get_executables():
            fd = 'fd'

        if fd is not None:
            hidden = ('--hidden' if self.fm.settings.show_hidden else '')
            exclude = "--no-ignore-vcs --exclude '.git' --exclude '*.py[co]' --exclude '__pycache__'"
            only_directories = ('--type directory' if self.quantifier else '')
            fzf_default_command = '{} --follow {} {} {} --color=always'.format(
                fd, hidden, exclude, only_directories
            )
        else:
            hidden = ('-false' if self.fm.settings.show_hidden else r"-path '*/\.*' -prune")
            exclude = r"\( -name '\.git' -o -name '*.py[co]' -o -fstype 'dev' -o -fstype 'proc' \) -prune"
            only_directories = ('-type d' if self.quantifier else '')
            fzf_default_command = 'find -L . -mindepth 1 {} -o {} -o {} -print | cut -b3-'.format(
                hidden, exclude, only_directories
            )

        env = os.environ.copy()
        env['FZF_DEFAULT_COMMAND'] = fzf_default_command
        env['FZF_DEFAULT_OPTS'] = '--height=40% --layout=reverse --ansi --preview="{}"'.format('''
            (
                batcat --color=always {} ||
                bat --color=always {} ||
                cat {} ||
                tree -ahpCL 3 -I '.git' -I '*.py[co]' -I '__pycache__' {}
            ) 2>/dev/null | head -n 100
        ''')

        fzf = self.fm.execute_command('fzf --no-multi', env=env,
                                      universal_newlines=True, stdout=subprocess.PIPE)
        stdout, _ = fzf.communicate()
        if fzf.returncode == 0:
            selected = os.path.abspath(stdout.strip())
            if os.path.isdir(selected):
                self.fm.cd(selected)
            else:
                self.fm.select_file(selected)


# Locate a file in the home directory with fzf
# Source: https://github.com/ranger/ranger/wiki/Custom-Commands#search-home-directory-with-fzf
class fzf_locate(Command):
    """
    :fzf_locate
    Find a file using fzf.
    With a prefix argument select only directories.
    See: https://github.com/junegunn/fzf
    """
    def execute(self):
        import subprocess
        if self.quantifier:
            command="locate home | fzf -e -i"
        else:
            command="locate home | fzf -e -i"
        fzf = self.fm.execute_command(command, stdout=subprocess.PIPE)
        stdout, stderr = fzf.communicate()
        if fzf.returncode == 0:
            fzf_file = os.path.abspath(stdout.decode('utf-8').rstrip('\n'))
            if os.path.isdir(fzf_file):
                self.fm.cd(fzf_file)
            else:
                self.fm.select_file(fzf_file)


# Source: https://github.com/ranger/ranger/wiki/Custom-Commands#search-file-content-in-current-directory-recursively-with-fzf-and-open-target-with-neovim
class fzf_content_open(Command):
    """
    :fzf_content_open
    Pre-requisites: fzf, rg, bat, awk, vim or neovim
    Using `rg` to search file content recursively in current directory.
    Filtering with `fzf` and preview with `bat`.
    Pressing `Enter` on target will open at line in (neo)vim.
    """

    def execute(self):
        import subprocess
        import os
        from ranger.ext.get_executables import get_executables

        if 'rg' in get_executables():
            rg = 'rg'
        else:
            self.fm.notify("Couldn't find rg in the PATH.", bad=True)
            return

        if 'fzf' in get_executables():
            fzf = 'fzf'
        else:
            self.fm.notify("Couldn't find fzf in the PATH.", bad=True)
            return

        if 'bat' in get_executables():
            bat = 'bat'
        else:
            self.fm.notify("Couldn't find bat in the PATH.", bad=True)
            return

        editor = None
        if 'nvim' in get_executables():
            editor = 'nvim'
        elif 'vim' in get_executables():
            editor = 'vim'

        if rg is not None and fzf is not None and bat is not None and editor is not None:
            # we should not recursively search through all file content from home directory
            if (self.fm.thisdir.path == self.fm.home_path):
                self.fm.notify("Searching from home directory is not allowed", bad=True)
                return
            fzf = self.fm.execute_command(
                'rg --line-number "${1:-.}" | fzf --delimiter \':\' \
                    --preview \'bat --color=always --highlight-line {2} {1}\' \
                    | awk -F \':\' \'{print "+"$2" "$1}\'',
                universal_newlines=True,stdout=subprocess.PIPE)

            stdout, _ = fzf.communicate()
            if fzf.returncode == 0:
                if len(stdout) < 2:
                    return

                selected_line = stdout.split()[0]
                full_path = stdout.split()[1].strip()

                file_fullpath = os.path.abspath(full_path)
                file_basename = os.path.basename(full_path)

                if os.path.isdir(file_fullpath):
                    self.fm.cd(file_fullpath)
                else:
                    self.fm.select_file(file_fullpath)

                self.fm.execute_command(editor + " " + selected_line + " " + file_basename)


# Source: https://github.com/ranger/ranger/wiki/Custom-Commands#ripgrep-all--fzf-integration
class fzf_rga_documents_search(Command):
    """
    :fzf_rga_search_documents
    Search in PDFs, E-Books and Office documents in current directory.
    Allowed extensions: .epub, .odt, .docx, .fb2, .ipynb, .pdf.

    Usage: fzf_rga_search_documents <search string>
    """
    def execute(self):
        if self.arg(1):
            search_string = self.rest(1)
        else:
            self.fm.notify("Usage: fzf_rga_search_documents <search string>", bad=True)
            return

        import subprocess
        import os.path
        from ranger.container.file import File
        command="rga '%s' . --rga-adapters=pandoc,poppler | fzf +m | awk -F':' '{print $1}'" % search_string
        fzf = self.fm.execute_command(command, universal_newlines=True, stdout=subprocess.PIPE)
        stdout, stderr = fzf.communicate()
        if fzf.returncode == 0:
            fzf_file = os.path.abspath(stdout.rstrip('\n'))
            self.fm.execute_file(File(fzf_file))
