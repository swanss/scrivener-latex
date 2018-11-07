#!/usr/bin/env python3
"""Converts scrivener multimarkdown files to docx, tex and pdf (at once)."""

import argparse
from glob import glob
import os
import sys
import subprocess
import re
from pprint import pprint


def get_file_if_unique(location, ext):
    """Find file if unique for the provided extension."""
    files = glob(os.path.join(location, ext))
    if len(files) == 1:
        return files[0]
    else:
        print(
            'Multiple/No ' + ext[1:] + ' files found in the working directory.'
            'Specify one please.')
        sys.exit()


def find_in_texfile(tex_content, matchstr, unique=True):
    """Find matchstr in tex_content list."""
    doc_match = [i for i, line in enumerate(tex_content)
                 if matchstr in line]

    if unique:
        if not (len(doc_match) == 1):
            print('Multiple/No ' + matchstr + ' found in generated tex file.')
            sys.exit()
        else:
            doc_match = doc_match[0]
        return doc_match
    else:
        return doc_match


def crop_pdfs(src, dest, margins):
    """Crop pdfs in src and place in dest."""
    files = glob(os.path.join(src, '*.pdf'))
    if not os.path.exists(dest):
        os.makedirs(dest)

    for pdf in files:
        _, filename = os.path.split(pdf)
        subprocess.run(["pdfcrop", "--margins", margins,
                        os.path.join(src, filename),
                        os.path.join(dest, filename)])


def split_figure_tex(tex_content, dest):
    """Split figure tex file into individual files."""
    fig_start = find_in_texfile(tex_content, "\\begin{figure}", False)
    fig_end = find_in_texfile(tex_content, "\\end{figure}", False)
    label_lines = find_in_texfile(tex_content, "\\label{", False)

    # Check for consistency in counts
    if not (len(fig_start) == len(fig_end)) and (
            len(fig_start) == len(label_lines)):

        print('Unequal begin{figure} (' +
              str(len(fig_start)) + '), end{figure} ('
              + str(len(fig_end)) + ') and label ('
              + str(len(label_lines)) + ') found.')
        sys.exit()

    else:
        # Find label name (will become filename)
        p = re.compile('label{(\S+)}')
        tex_names = []
        for line in label_lines:
            temp = p.search(tex_content[line])
            if len(temp.groups()) != 1:
                print('Something is off with label detection')
                sys.exit()
            else:
                tex_names.append(temp.groups()[0])

        # Create folder if it does not exist
        if not os.path.exists(dest):
            os.makedirs(dest)

        # Write individual figure tex file
        for i, tex in enumerate(tex_names):
            tex_output = tex_content[fig_start[i]:fig_end[i] + 1] + ["\n"]
            # Write complete tex file
            with open(os.path.join(dest, tex) + '.tex', 'w') as tex_file:
                tex_file.writelines(tex_output)


def parseArguments(args):
    """Properly parse input arguments."""
    if not args.bibfile:
        args.bibfile = get_file_if_unique(args.location, '*.bib')
    if not args.maintex:
        args.maintex = get_file_if_unique(args.location, '*main.tex')
    if not args.outfile:
        args.outfile = os.path.splitext(args.mmd[0])[0]
    if not args.figure_source:
        args.figure_source = os.path.join(args.location, 'figures')
    if not args.figuretex:
        args.figuretex = os.path.join(args.figure_source, 'all-figures.tex')
    if not args.figure_dest:
        args.figure_dest = os.path.join(args.figure_source, 'cropped')
    if not args.tex_folder:
        args.tex_folder = os.path.join(args.figure_source, 'texs')
    if not args.whitespace_margins:
        args.whitespace_margins = '0 20 0 20'

    return args


def main():
    """Parse input and generate documents."""
    parser = argparse.ArgumentParser(
        description=(
            'Converts scrivener mmd outputs to docx, tex and pdf. '
            'Integrates it with input and footer tex file, if available.'))

    parser.add_argument('mmd', nargs=1, type=str,
                        help='multimarkdown file to be converted')
    parser.add_argument(
        "-l", "--location", default=os.getcwd(), help="set working directory")
    parser.add_argument(
        "-b", "--bibfile", default=False,
        help="bibtex file used to generate bibliography.")
    parser.add_argument(
        "-m", "--maintex", default=False,
        help="main tex file that controls appearance.")
    parser.add_argument(
        "-o", "--outfile", default=False,
        help="outfile prefix for generated files.")
    parser.add_argument(
        "-f", "--figuretex", default=False,
        help="Tex file containing figure code chunks.")
    parser.add_argument(
        "-s", "--figure-source", default=False,
        help="source folder containing figures.")
    parser.add_argument(
        "-d", "--figure-dest", default=False,
        help="destination folder for cropped figures.")
    parser.add_argument(
        "-w", "--whitespace-margins", default=False,
        help="white space margins for cropped figures.")
    parser.add_argument(
        "-t", "--tex-folder", default=False,
        help="destination folder for individual figure tex files.")
    parser.add_argument(
        "-n", "--only-figures", default=False, action='store_true',
        help="generate only figures (no main thesis file).")

    args = parseArguments(parser.parse_args())

    # Change location to the main folder as the working directory
    os.chdir(args.location)

    """Generate figures pdf"""
    # Crop pdfs for figures
    crop_pdfs(args.figure_source, args.figure_dest, args.whitespace_margins)
    # find start point
    with open(args.maintex, 'r') as tex_file:
        main_tex_content = tex_file.readlines()
    main_start = find_in_texfile(main_tex_content, "\\begin{document}")
    # Create a figures pdf
    figure_tex_file = main_tex_content[:main_start + 1] + \
        ["\\input{"] + [os.path.relpath(args.figuretex, args.location)] + \
        ["}\n", "\\end{document}\n", "\n"]
    with open(args.outfile + '-only-figures.tex', 'w') as tex_file:
        tex_file.writelines(figure_tex_file)
    # Compile tex and bib files
    subprocess.run(["pdflatex", args.outfile + '-only-figures.tex'])
    subprocess.run(["pdflatex", args.outfile + '-only-figures.tex'])

    """Generate main pdf"""
    if not args.only_figures:
        # Split figure tex file
        with open(args.figuretex, 'r') as tex_file:
            figure_tex_content = tex_file.readlines()
        split_figure_tex(figure_tex_content, args.tex_folder)

        # Generate docx file from multimarkdown
        subprocess.run(["pandoc", "-s", "-S", "--normalize",
                        "--bibliography", args.bibfile, "--toc",
                        "-f", "markdown", "-t", "docx",
                        "-o", args.outfile + ".docx", args.mmd[0]])

        # Generate temp tex file
        subprocess.run(["pandoc", "-s", "-S", "--normalize",
                        "--natbib", "-f", "markdown", "-t", "latex",
                        "-o", "scrivener_mmd_compile_temp.tex", args.mmd[0],
                        "--variable", "documentclass=report"])

        # Read temp, main tex file
        with open('scrivener_mmd_compile_temp.tex', 'r') as tex_file:
            input_tex_content = tex_file.readlines()
        # find start, input and stop in tex files
        doc_start = find_in_texfile(input_tex_content, "\\begin{document}")
        doc_stop = find_in_texfile(input_tex_content, "\\end{document}")
        input_line = find_in_texfile(
            main_tex_content, "\\input{scrivener-input.tex}")

        # Concatenate to create a complete tex file
        complete_tex_file = main_tex_content[:input_line] + \
            input_tex_content[doc_start + 1:doc_stop] + \
            main_tex_content[input_line + 1:]

        # Write complete tex file
        with open(args.outfile + '.tex', 'w') as tex_file:
            tex_file.writelines(complete_tex_file)

        # Compile tex and bib files
        subprocess.run(["pdflatex", args.outfile + '.tex'])
        subprocess.run(["bibtex", args.outfile + '.aux'])
        subprocess.run(["pdflatex", args.outfile + '.tex'])
        subprocess.run(["pdflatex", args.outfile + '.tex'])

    # Print exit message
    print("Scrivener mmd has been exported as docx, tex and pdf")


if __name__ == '__main__':
    main()
