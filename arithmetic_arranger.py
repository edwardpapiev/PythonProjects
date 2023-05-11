import re
def arithmetic_arranger(problems, boolean_option = None):
    str_line_one = ''
    str_line_two = ''
    str_line_three = ''
    str_line_four = ''
    arranged_problems = ''
    problem_count = len(problems)
    space = ' '
    dash = '-'
    for problem in problems:
        indv_items = problem.split()
        if problem_count >= 6:
            arranged_problems = 'Error: Too many problems.'
            return arranged_problems
        elif indv_items[1] != '+' and indv_items[1] != '-':
            arranged_problems = 'Error: Operator must be \'+\' or \'-\'.'
            return arranged_problems
        elif bool(re.search('\D+', indv_items[0])) is True or bool(re.search('\D+', indv_items[2])) is True:
            arranged_problems = 'Error: Numbers must only contain digits.'
            return arranged_problems
        elif len(indv_items[0]) > 4 or len(indv_items[2]) > 4:
            arranged_problems = 'Error: Numbers cannot be more than four digits.'
            return arranged_problems
    if boolean_option == None:
        for problem in problems:
            indv_items = problem.split()
            if len(indv_items[0]) >= len(indv_items[2]):
                str_line_one = str_line_one + '  ' + indv_items[0] + '    '
                str_line_two = str_line_two + indv_items[1] + ' ' + space * (len(indv_items[0]) - len(indv_items[2])) + indv_items[2] + '    '
                str_line_three = str_line_three + dash * (2 + len(indv_items[0])) + '    '
            elif len(indv_items[0]) < len(indv_items[2]):
                str_line_one = str_line_one + '  ' + space * (len(indv_items[2]) - len(indv_items[0])) + indv_items[0] + '    '
                str_line_two = str_line_two + indv_items[1] + ' ' + indv_items[2] + '    '
                str_line_three = str_line_three + dash * (2 + len(indv_items[2])) + '    '
        arranged_problems = str_line_one.rstrip() + '\n' + str_line_two.rstrip() + '\n' + str_line_three.rstrip()

    elif boolean_option == True:
        for problem in problems:
            indv_items = problem.split()
            num1 = int(indv_items[0])
            num2 = int(indv_items[2])
            if len(indv_items[0]) >= len(indv_items[2]):
                str_line_one = str_line_one + '  ' + indv_items[0] + '    '
                str_line_two = str_line_two + indv_items[1] + ' ' + space * (len(indv_items[0]) - len(indv_items[2])) + indv_items[2] + '    '
                dash_number = (2 + len(indv_items[0]))
                str_line_three = str_line_three + dash * dash_number + '    '
                x = indv_items[1]
                answer = lambda x: num1 + num2 if x == '+' else num1 - num2
                realans = str(answer(indv_items[1]))
                str_line_four = str_line_four + space * (dash_number - len(realans)) + realans + space*4
            elif len(indv_items[0]) < len(indv_items[2]):
                str_line_one = str_line_one + '  ' + space * (len(indv_items[2]) - len(indv_items[0])) + indv_items[0] + '    '
                str_line_two = str_line_two + indv_items[1] + ' ' + indv_items[2] + '    '
                dash_number = (2 + len(indv_items[2]))
                str_line_three = str_line_three + dash * dash_number + '    '
                x = indv_items[1]
                answer = lambda x: num1 + num2 if x == '+' else num1 - num2
                realans = str(answer(indv_items[1]))
                str_line_four = str_line_four + space * (dash_number - len(realans)) + realans + space*4
        arranged_problems = str_line_one.rstrip() + '\n' + str_line_two.rstrip() + '\n' + str_line_three.rstrip() + '\n' + str_line_four.rstrip()
    return arranged_problems

