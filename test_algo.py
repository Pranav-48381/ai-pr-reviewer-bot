def find_two_sum(numbers, target):
    """
    Finds two numbers in a list that add up to a target sum.
    Returns a list of tuples containing the pairs.
    """
    result = []
    
    # Inefficient nested loop approach
    for i in range(len(numbers)):
        for j in range(len(numbers)):
            if numbers[i] + numbers[j] == target:
                result.append((numbers[i], numbers[j]))
                
    return result

# Test execution
my_nums = [2, 7, 11, 15]
print(find_two_sum(my_nums, 9))
